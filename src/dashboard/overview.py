"""Overview panels from recorded service reads, without operational side effects."""

from datetime import datetime, timedelta, timezone
from html import escape

import altair as alt
import pandas as pd
import streamlit as st
from adapter import (
    decision_state,
    normalize_decisions,
    number,
    read_resource,
    runtime_policy,
    timestamp,
)

WIB = timezone(timedelta(hours=7))


def mapping(value):
    return value if isinstance(value, dict) else {}


def title(name, note):
    st.html(f'<h2 class="panel-title">{escape(name)}</h2><p class="panel-note">{escape(note)}</p>')


def facts(items):
    st.html(
        "".join(
            f'<div class="fact-row"><span>{escape(str(label))}</span>'
            f"<b>{escape(str(value))}</b></div>"
            for label, value in items
        )
    )


def chart_style(chart, palette, height):
    return (
        chart.properties(height=height)
        .configure(background=palette["surface"], font="Geist")
        .configure_view(strokeWidth=0)
        .configure_axis(
            gridColor=palette["chart-grid"],
            domain=False,
            tickColor=palette["chart-grid"],
            labelColor=palette["text-muted"],
            titleColor=palette["text-muted"],
            labelFontSize=11,
            titleFontSize=11,
            labelOverlap=True,
        )
        .configure_legend(labelColor=palette["text-secondary"], title=None)
    )


def render_overview(base_url, palette, interval):
    @st.fragment(run_every=interval)
    def render():
        with st.spinner("Reading model, decisions, actions, audit and drift sources…"):
            sources = {
                path: read_resource(base_url, path, shape)
                for path, shape in (
                    ("/health", dict),
                    ("/scaling/decisions", list),
                    ("/scaling/actions", list),
                    ("/operations/audit", dict),
                    ("/monitoring/drift", dict),
                )
            }
        health = sources["/health"]["data"]
        audit = sources["/operations/audit"]["data"]
        drift = sources["/monitoring/drift"]["data"]
        decisions = sources["/scaling/decisions"]
        now = datetime.now(timezone.utc)
        rows, rejected = normalize_decisions(decisions["data"])
        state = decision_state(rows, rejected, decisions["error"], now, interval or 15)
        latest = rows[-1] if rows else None
        policy = runtime_policy(health)
        synthetic = any(row["synthetic"] for row in rows)
        serving = health.get("status") == "healthy" and health.get("model_ready") is True
        version = str(health.get("model_version") or "Unknown")
        status_label = {
            "ready": "Recent observations",
            "stale": "Stale observations",
            "empty": "No observations",
            "error": "Source error",
        }[state]
        if synthetic:
            st.warning(
                "Synthetic telemetry reported by the source. These are not measured results."
            )
        st.html(
            f'<div role="status"><span class="status status-{state}">{status_label}</span>'
            f' <span class="panel-note">Fetched {now.astimezone(WIB):%H:%M:%S} WIB · '
            f"{len(rows)} validated samples</span></div>"
        )
        if state == "error":
            st.error(
                "Decision source failed validation or could not be read. Use Refresh now to retry."
            )
        elif state == "empty":
            st.info(
                "The decision buffer is empty. Refresh after the controller records an evaluation."
            )
        elif state == "stale":
            st.warning(
                "Last-known observations are shown below. The controller has not supplied a recent sample."
            )
        if rejected:
            st.caption(
                f"Excluded {rejected} invalid decision record(s). Missing measurements are not zero."
            )

        with st.container(key="overview-metrics"):
            cols = st.columns(4, gap="small")
            with cols[0]:
                st.metric(
                    "Serving Engine",
                    "Ready" if serving else "Unavailable",
                    delta="Model loaded" if serving else "Inspect Model Health",
                    delta_color="off",
                    help="Requires a successful health read, healthy status and model_ready=true.",
                )
            with cols[1]:
                st.metric(
                    "Active Model",
                    version,
                    delta=str(health.get("model_algorithm") or "Algorithm unavailable"),
                    delta_color="off",
                )
            with cols[2]:
                st.metric(
                    "Observed Replicas",
                    str(latest["observed_replicas"]) if latest else "Unknown",
                    delta=f"Policy {policy['minimum']}–{policy['maximum']} pods"
                    if policy
                    else "Policy unavailable",
                    delta_color="off",
                )
            with cols[3]:
                st.metric(
                    "Next-minute Forecast",
                    f"{latest['forecast_rps']:.1f} req/s" if latest else "Unknown",
                    delta="Point forecast · +60s",
                    delta_color="off",
                )

        df = pd.DataFrame(rows)
        if latest:
            df["observed_wib"] = (
                pd.to_datetime(df["issued_at_utc"]).dt.tz_convert(WIB).dt.tz_localize(None)
            )
            df["target_wib"] = (
                pd.to_datetime(df["forecast_target_utc"]).dt.tz_convert(WIB).dt.tz_localize(None)
            )
            observed = latest["issued_at_utc"].astimezone(WIB).strftime("%d %b %H:%M:%S WIB")
            df["segment"] = (df["issued_at_utc"].diff().dt.total_seconds() > 45).cumsum()
            available = f"{len(rows)} samples · {df['observed_wib'].min():%H:%M:%S}–{df['observed_wib'].max():%H:%M:%S} WIB"
        else:
            observed = "Unknown"
            available = "No validated samples"

        actions = []
        for row in sources["/scaling/actions"]["data"]:
            try:
                if not isinstance(row, dict):
                    continue
                actions.append({**row, "observed": timestamp(row["timestamp"])})
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
        actions.sort(key=lambda row: row["observed"], reverse=True)

        with st.container(key="overview-grid"):
            primary, secondary = st.columns([1.78, 1], gap="medium")
            with primary:
                with st.container(key="panel-forecast"):
                    title(
                        "Workload Forecast",
                        "Actual workload and latest +60s point forecast · req/s",
                    )
                    if latest:
                        base = alt.Chart(df).encode(
                            detail="segment:N",
                            x=alt.X(
                                "observed_wib:T",
                                title="Time (WIB)",
                                axis=alt.Axis(format="%H:%M", tickCount=4),
                            ),
                        )
                        actual = base.mark_line(
                            color=palette["chart-actual"], strokeWidth=2, point={"size": 12}
                        ).encode(
                            y=alt.Y("actual_rps:Q", title="req/s", scale=alt.Scale(zero=True)),
                            tooltip=[
                                alt.Tooltip(
                                    "observed_wib:T", title="Observed (WIB)", format="%H:%M:%S"
                                ),
                                alt.Tooltip("actual_rps:Q", title="Actual req/s", format=".2f"),
                            ],
                        )
                        area = base.mark_area(color=palette["chart-actual"], opacity=0.07).encode(
                            y="actual_rps:Q"
                        )
                        forecast = (
                            alt.Chart(df.tail(1))
                            .mark_point(
                                color=palette["chart-predicted"],
                                filled=True,
                                size=65,
                                shape="diamond",
                            )
                            .encode(
                                x="target_wib:T",
                                y="forecast_rps:Q",
                                tooltip=[
                                    alt.Tooltip(
                                        "target_wib:T", title="Target (WIB)", format="%H:%M:%S"
                                    ),
                                    alt.Tooltip(
                                        "forecast_rps:Q", title="Forecast req/s", format=".2f"
                                    ),
                                ],
                            )
                        )
                        guide = (
                            alt.Chart(
                                pd.DataFrame(
                                    [
                                        {
                                            "time": df.iloc[-1]["observed_wib"],
                                            "value": latest["actual_rps"],
                                        },
                                        {
                                            "time": df.iloc[-1]["target_wib"],
                                            "value": latest["forecast_rps"],
                                        },
                                    ]
                                )
                            )
                            .mark_line(
                                color=palette["chart-predicted"], strokeDash=[5, 4], strokeWidth=2
                            )
                            .encode(x="time:T", y="value:Q")
                        )
                        chart = area + actual + guide + forecast
                        if policy:
                            capacity = base.mark_line(
                                color=palette["chart-capacity"],
                                strokeDash=[2, 3],
                                interpolate="step-after",
                            ).encode(y="capacity_rps:Q")
                            df["capacity_rps"] = df["observed_replicas"] * policy["capacity"]
                            chart += capacity
                        st.altair_chart(
                            chart_style(chart, palette, 192),
                            width="stretch",
                            theme=None,
                            alt="Actual workload in blue, latest forecast at target time +60 seconds in teal, policy capacity dotted.",
                        )
                        st.caption(
                            "Blue: actual · Teal dashed: guide to one forecast, not intermediate outputs · Dotted: observed policy capacity"
                        )
                    else:
                        st.info(
                            "Workload chart needs a valid controller observation. Retry with Refresh now."
                        )
                    st.caption(
                        f"{available}. Full 15m/30m/1h retention is not guaranteed by this buffer."
                    )

                with st.container(key="panel-scaling"):
                    title(
                        "Scaling Decisions",
                        "Observed and recommended replicas · decision-loop evidence",
                    )
                    if latest:
                        base = alt.Chart(df).encode(
                            detail="segment:N",
                            x=alt.X(
                                "observed_wib:T",
                                title="Time (WIB)",
                                axis=alt.Axis(format="%H:%M", tickCount=4),
                            ),
                        )
                        observed_line = base.mark_line(
                            color=palette["chart-actual"],
                            interpolate="step-after",
                            strokeWidth=2,
                            point=True,
                        ).encode(
                            y=alt.Y(
                                "observed_replicas:Q",
                                title="Replicas",
                                scale=alt.Scale(zero=True),
                                axis=alt.Axis(tickMinStep=1),
                            ),
                            tooltip=[
                                alt.Tooltip(
                                    "observed_wib:T", title="Observed (WIB)", format="%H:%M:%S"
                                ),
                                "observed_replicas:Q",
                            ],
                        )
                        recommended = base.mark_line(
                            color=palette["chart-predicted"],
                            interpolate="step-after",
                            strokeDash=[5, 4],
                        ).encode(y="recommended_replicas:Q", tooltip=["recommended_replicas:Q"])
                        scaling = observed_line + recommended
                        if policy:
                            scaling += (
                                alt.Chart(pd.DataFrame([{"maximum": policy["maximum"]}]))
                                .mark_rule(color=palette["chart-threshold"], strokeDash=[3, 3])
                                .encode(y="maximum:Q")
                            )
                        st.altair_chart(
                            chart_style(scaling, palette, 192),
                            width="stretch",
                            theme=None,
                            alt="Observed replicas solid blue, recommendations dashed teal, runtime maximum dotted amber. This is not a pod readiness census.",
                        )
                        st.caption(
                            "Solid: observed · Dashed: recommended · Amber: runtime maximum. Applied operations are listed separately."
                        )
                    else:
                        st.info(
                            "Scaling chart needs valid replica observations. No ready-pod count is inferred."
                        )
                    with st.expander("Inspect observations / export CSV"):
                        st.caption(
                            "UTC issue and target times are distinct. synthetic is source-reported."
                        )
                        if rows:
                            export = pd.DataFrame(rows)
                            st.dataframe(export, hide_index=True, width="stretch")
                            st.download_button(
                                "Export observations CSV",
                                export.to_csv(index=False),
                                "titipin-observations.csv",
                                "text/csv",
                                on_click="ignore",
                            )
                        else:
                            st.caption("Export unavailable: no validated observations.")

            with secondary:
                with st.container(key="panel-model"):
                    title("Model Health", "Readiness and evaluation sources")
                    st.html(
                        f'<span class="status status-{"ready" if serving else "error"}">{"Model ready" if serving else "Readiness unavailable"}</span>'
                    )
                    retrain = mapping(mapping(audit.get("retraining")).get("latest"))
                    facts(
                        [
                            (
                                "Model / alias",
                                f"{version} / {health.get('model_alias') or 'Unknown'}",
                            ),
                            ("Validation MAE", retrain.get("val_mae") or "Unavailable"),
                            ("Online forecast MAE", "Aligned history required"),
                        ]
                    )
                    try:
                        psi = number(drift["psi_score"])
                        cycles = number(drift["evaluated_cycles"])
                        psi_text = (
                            f"{psi:.3f} · {int(cycles)} cycles"
                            if cycles >= 3
                            else "Insufficient evidence (<3 cycles)"
                        )
                    except (KeyError, TypeError, ValueError):
                        psi_text = "Unavailable"
                    facts([("PSI (reference)", psi_text)])
                    st.caption(
                        "PSI uses a demo/reference baseline. Health observation age is unknown."
                    )
                    with st.expander("Inspect model provenance"):
                        st.caption(
                            "Validation MAE is stored training metadata, not online error or proof of the serving model's quality. Health fetch time is not observation time."
                        )

                with st.container(key="panel-cluster"):
                    title(
                        "Cluster Status", "Replica observations, not a Kubernetes readiness census"
                    )
                    facts(
                        [
                            (
                                "Observed replicas",
                                latest["observed_replicas"] if latest else "Unknown",
                            ),
                            (
                                "Recommended replicas",
                                latest["recommended_replicas"] if latest else "Unknown",
                            ),
                            (
                                "Runtime capacity",
                                f"{policy['capacity']:g} req/s/pod"
                                if policy
                                else "Unavailable / invalid policy",
                            ),
                        ]
                    )
                    if latest and policy:
                        # shortcut: at most 32 slots; use a numeric census for larger policies.
                        slots = "".join(
                            f'<span class="pod-slot {"observed" if i < latest["observed_replicas"] else ""}"></span>'
                            for i in range(min(policy["maximum"], 32))
                        )
                        st.html(f'<div class="pod-slots" aria-hidden="true">{slots}</div>')
                    st.caption(
                        "Ready pods, node readiness and CPU/RAM saturation: unavailable. Scaler mode: unknown / not exposed."
                    )

                with st.container(key="panel-events"):
                    title("Recent Events", "Recorded operations · not joined to recommendations")
                    if sources["/scaling/actions"]["error"]:
                        st.error("Action source unavailable. Retry the read with Refresh now.")
                    elif not actions:
                        st.caption(
                            "No valid action records. A recommendation alone does not prove a change was applied."
                        )
                    else:
                        st.html(
                            '<ul class="events">'
                            + "".join(
                                f"<li><time>{action['observed'].astimezone(WIB):%H:%M:%S} WIB</time>"
                                f"{escape(str(action.get('action', 'Unknown')))} "
                                f"{escape(str(action.get('from_replicas', '?')))} → {escape(str(action.get('to_replicas', '?')))}"
                                f" · {escape(str(action.get('status', 'Unknown')))}"
                                f"{' · synthetic' if action.get('synthetic') else ''}</li>"
                                for action in actions[:4]
                            )
                            + "</ul>"
                        )
                        with st.expander("Inspect recorded operations"):
                            st.dataframe(
                                pd.DataFrame(actions).drop(columns=["observed"]),
                                hide_index=True,
                                width="stretch",
                            )

        with st.container(key="overview-bottom"):
            summary, slo = st.columns(2, gap="medium")
            with summary, st.container(key="panel-summary"):
                title("Decision Summary", "Recommendation and runtime policy")
                if latest:
                    st.html(
                        f'<p class="summary">Recommend <b>{latest["observed_replicas"]} → {latest["recommended_replicas"]} replicas</b>'
                        f' for <span class="forecast-value">{latest["forecast_rps"]:.2f} req/s</span> at '
                        f"{latest['forecast_target_utc'].astimezone(WIB):%H:%M:%S} WIB (+60s).</p>"
                    )
                    if policy:
                        st.caption(
                            f"Policy: ceil(forecast / {policy['capacity']:g} req/s/pod), bounded to [{policy['minimum']}, {policy['maximum']}]. Recorded recommendation shown; application is unverified."
                        )
                    else:
                        st.caption(
                            "Policy is unavailable or invalid; capacity arithmetic is withheld."
                        )
                else:
                    st.caption(
                        "No recommendation available. Wait for a valid controller observation, then refresh."
                    )
            with slo, st.container(key="panel-slo"):
                title("SLO Snapshot", "Latest decision input · not an approved SLO window")
                facts(
                    [
                        (
                            "Observed p95",
                            f"{latest['p95_latency_ms']:.1f} ms" if latest else "Unknown",
                        ),
                        ("HTTP success rate", "Unavailable: request counts required"),
                        ("CPU saturation", "Unavailable: denominator required"),
                    ]
                )
        failures = [path for path, source in sources.items() if source["error"]]
        if failures:
            st.caption(
                "Unavailable sources: " + ", ".join(failures) + ". Valid panels remain independent."
            )
        st.caption(
            f"Observed: {observed} · Fetched: {now.astimezone(WIB):%d %b %H:%M:%S} WIB · Source: recorded decisions · Horizon: 60s · State: {state}"
        )

    render()

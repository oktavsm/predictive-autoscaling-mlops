#!/usr/bin/env python3
"""Titipin MLOps console. Overview is read-only; operational actions stay explicit."""

import base64
import json
import math
import os
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from re import sub

import pandas as pd
import requests
import streamlit as st
from adapter import number, read_resource, runtime_policy
from overview import facts, mapping, render_overview

INFERENCE_API_URL = (
    os.getenv("INFERENCE_API_URL")
    or os.getenv("INFERENCE_SERVICE_URL")
    or os.getenv("INFERENCE_URL")
    or "http://localhost:8000"
)
PUBLIC_INFERENCE_DOCS = os.getenv("PUBLIC_INFERENCE_DOCS", "https://model.titipin.me/docs")
MLFLOW_URL = os.getenv("MLFLOW_URL", "https://mlflow.titipin.me")
GRAFANA_URL = os.getenv("GRAFANA_URL", "https://grafana.titipin.me")
MINIO_URL = os.getenv("MINIO_URL", "https://minio.titipin.me")
API_URL = os.getenv("API_URL", "https://api.titipin.me")
ASSETS = Path(__file__).parent / "assets"

st.set_page_config(
    page_title="Titipin MLOps",
    page_icon=str(ASSETS / "logo/mark-accent.svg"),
    layout="wide",
    initial_sidebar_state="auto",
)
# shortcut: Streamlit reports a changed menu theme on rerun; use Refresh now to apply it.
theme = st.context.theme.type or "dark"
palette = {
    key: value["$value"]
    for key, value in json.loads((ASSETS / "tokens.json").read_text())["color"][theme].items()
}
variables = ";".join(f"--{key}:{value}" for key, value in palette.items())
fonts = ""
for family, filename in (
    ("Geist", "Geist-Variable.woff2"),
    ("Geist Mono", "GeistMono-Variable.woff2"),
):
    encoded = base64.b64encode((ASSETS / "fonts" / filename).read_bytes()).decode()
    fonts += (
        f'@font-face{{font-family:"{family}";src:url(data:font/woff2;base64,{encoded}) '
        'format("woff2");font-weight:100 900;font-display:swap;}'
    )
st.html(
    f"<style>{fonts}:root{{{variables};--font-sans:Geist,system-ui,sans-serif;"
    f'--font-mono:"Geist Mono",ui-monospace,monospace;}}'
    f"{(ASSETS / 'dashboard.css').read_text()}</style>"
)
st.logo(
    str(ASSETS / f"logo/lockup-{theme}.svg"),
    icon_image=str(ASSETS / "logo/mark-accent.svg"),
    size="large",
)

pages = {
    "Overview": "overview",
    "Scaling Simulator": "sim",
    "Drift & Retraining": "retrain",
    "Model Registry": "registry",
    "Cluster Architecture": "k8s",
    "HPA vs Predictive": "benchmark",
    "Telemetry Audit": "audit",
    "FinOps & Carbon": "finops",
    "Workload Injector": "injector",
}
with st.sidebar:
    st.html('<p class="brand-caption">Predictive Autoscaling<br>Control Plane</p>')
    with st.container(key="workspace"):
        page_title = st.radio(
            "Workspace", list(pages), label_visibility="collapsed", width="stretch"
        )
    page = pages[page_title]
    st.divider()
    can_auto_refresh = page in ("overview", "injector", "audit", "registry", "benchmark")
    auto_refresh = st.toggle("Auto-refresh", value=True, disabled=not can_auto_refresh)
    refresh_rate = st.select_slider(
        "Read interval",
        options=[5, 10, 15, 30],
        value=15,
        format_func=lambda seconds: f"{seconds}s",
        disabled=not auto_refresh or not can_auto_refresh,
    )
    if st.button("Refresh now", width="stretch"):
        st.rerun()
    if not can_auto_refresh:
        st.caption("Reads in this workspace are manual.")
    with st.expander("Connected services"):
        for name, url in (
            ("Grafana Observability", GRAFANA_URL),
            ("MLflow Model Registry", MLFLOW_URL),
            ("MinIO / DVC Storage", MINIO_URL),
            ("Inference API Docs", PUBLIC_INFERENCE_DOCS),
            ("Laravel Target API", API_URL),
        ):
            st.link_button(name, url, width="stretch")
    st.caption("Design kit v1.1.0 · Change the app menu theme, then Refresh now")

st.html(
    '<a class="skip-link" href="#workspace-title">Skip to content</a>'
    f'<h1 id="workspace-title" tabindex="-1">{escape(page_title)}</h1>'
)
if page == "overview":
    st.caption("Serving evidence, next-minute workload, and recorded scaling decisions.")
    st.caption(
        "Source-reported metadata and decisions can include unmarked demo records in the current inference service. Verify production claims against Prometheus, MLflow and job logs."
    )
else:
    st.caption("Titipin MLOps · Operational workspace")


def heading(label, icon, note):
    glyph = sub(r"<title>.*?</title>", "", (ASSETS / f"icons/{icon}.svg").read_text())
    # Streamlit sanitizes inline SVG; a local data image preserves the kit geometry.
    glyph = base64.b64encode(
        glyph.replace("currentColor", palette["text-secondary"]).encode()
    ).decode()
    st.html(
        f'<h2 class="operation-title"><img src="data:image/svg+xml;base64,{glyph}" '
        f'width="20" height="20" alt="" aria-hidden="true">{escape(label)}</h2>'
        f'<p class="panel-note">{escape(note)}</p>'
    )


def read(path, shape=dict):
    source = read_resource(INFERENCE_API_URL, path, shape)
    if source["error"]:
        st.error(f"{path}: {source['error']}")
    return source["data"]


def post(path, payload):
    try:
        response = requests.post(f"{INFERENCE_API_URL.rstrip('/')}{path}", json=payload, timeout=5)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or not data:
            raise ValueError("Invalid response")
        return data
    except (requests.RequestException, ValueError, TypeError):
        st.error(
            "Request failed or returned an invalid response. No success was confirmed. Refresh status before retrying."
        )
        return None


def table(rows):
    if isinstance(rows, list) and rows and all(isinstance(row, dict) for row in rows):
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    elif rows:
        st.warning("Source returned an invalid table.")
    else:
        st.info("No records reported by this source.")


interval = int(refresh_rate) if auto_refresh and can_auto_refresh else None

if page == "overview":
    render_overview(INFERENCE_API_URL, palette, interval)

if page == "sim":
    health = read("/health")
    policy = runtime_policy(health)
    with st.sidebar.expander("Local simulation policy", expanded=True):
        st.caption("Preview only. These controls do not update the controller policy.")
        capacity = st.number_input(
            "Target req/s per pod",
            min_value=0.1,
            value=policy["capacity"] if policy else 10.0,
            step=1.0,
        )
        minimum = st.number_input(
            "Min replicas", min_value=1, value=policy["minimum"] if policy else 1
        )
        maximum = st.number_input(
            "Max replicas",
            min_value=minimum,
            value=max(minimum, policy["maximum"] if policy else 6),
        )
        if not policy:
            st.caption(
                "Runtime policy unavailable. Preview defaults: 10 req/s per pod, 1–6 replicas."
            )

    heading(
        "Forecast preview",
        "forecast",
        "Submit hypothetical telemetry to the serving model, then compare its recommendation with your local policy.",
    )
    st.info(
        "POST /predict updates inference counters and forecast gauges. It does not patch Kubernetes replicas or append to the scaling-decision buffer."
    )
    presets = {
        "Quiet (2 RPS)": (2.0, 0.08, 0.022, 95.0),
        "Normal (12.5 RPS)": (12.5, 0.32, 0.038, 130.0),
        "Surge (35 RPS)": (35.0, 0.85, 0.085, 165.0),
        "Flash sale (65 RPS)": (65.0, 1.45, 0.145, 210.0),
    }
    keys = ("sim_rps", "sim_cpu", "sim_p95", "sim_mem")
    for key, value in zip(keys, presets["Normal (12.5 RPS)"]):
        st.session_state.setdefault(key, value)
    with st.container(key="operation-presets"):
        for column, (label, values) in zip(st.columns(4), presets.items()):
            if column.button(label, width="stretch"):
                st.session_state.update(zip(keys, values))
    with st.container(key="panel-sim-inputs"):
        left, right = st.columns(2)
        rps = left.slider("Request rate (RPS)", 0.0, 90.0, step=0.5, key="sim_rps")
        cpu = left.slider("CPU usage (cores)", 0.0, 2.5, step=0.01, key="sim_cpu")
        p95 = right.slider("P95 latency (s)", 0.010, 0.400, step=0.001, key="sim_p95")
        memory = right.slider("PHP-FPM memory (MB)", 50.0, 500.0, step=1.0, key="sim_mem")
        if st.button("Compute forecast", type="primary", width="stretch"):
            st.session_state.pop("sim_result", None)
            now = datetime.now(timezone.utc)
            result = post(
                "/predict",
                {
                    "request_rate": rps,
                    "php_cpu_cores": cpu,
                    "p95_latency_seconds": p95,
                    "php_memory_mb": memory,
                    "hour": now.hour,
                    "minute": now.minute,
                    "current_replicas": max(minimum, min(maximum, math.ceil(rps / capacity))),
                },
            )
            if result is not None:
                try:
                    forecast = number(result["predicted_workload_rps_60s"])
                    replicas = number(result["recommended_replicas"])
                    if (
                        result.get("status") != "SUCCESS"
                        or not replicas.is_integer()
                        or replicas < 1
                    ):
                        raise ValueError("Invalid prediction")
                    st.session_state["sim_result"] = {
                        "response": result,
                        "inputs": dict(zip(keys, (rps, cpu, p95, memory))),
                        "forecast": forecast,
                        "replicas": int(replicas),
                    }
                except (KeyError, ValueError, TypeError, OverflowError):
                    st.error(
                        "Prediction response is incomplete or invalid. No forecast is available."
                    )
        st.caption(
            "Lag and rolling features are omitted; the inference service supplies its documented defaults."
        )
    if "sim_result" in st.session_state:
        result = st.session_state["sim_result"]
        if result["inputs"] != {key: st.session_state[key] for key in keys}:
            st.warning(
                "Inputs changed. Results below belong to the last submitted inputs; compute again to update them."
            )
        preview = max(minimum, min(maximum, math.ceil(result["forecast"] / capacity)))
        with st.container(key="operation-metrics"):
            cols = st.columns(3)
            cols[0].metric("Model forecast (+60s)", f"{result['forecast']:.1f} RPS")
            cols[1].metric("API recommended replicas", result["replicas"])
            cols[2].metric("Local policy preview", preview)
        st.caption(
            f"Local preview: ceil(forecast / {capacity:g}), bounded {minimum}–{maximum}. Replica readiness is not measured here."
        )
        with st.expander("Last submitted inputs and API response"):
            st.json({"inputs": result["inputs"], "response": result["response"]})


@st.fragment(run_every=interval)
def operational_view():
    if page == "injector":
        heading(
            "Traffic profiles",
            "pipeline",
            "Request a profile from the remote k6 daemon. Selection changes traffic against the configured target API.",
        )
        st.caption(
            "Profile sizes are configured VU ranges, not measured throughput or scaling guarantees. The daemon chooses the next profile after its current window."
        )
        live = read("/workload/status")
        alive = live.get("daemon_alive") is True
        with st.container(key="panel-daemon"):
            heading(
                "Generator status",
                "health",
                "Last state reported by the daemon; an accepted request still needs a heartbeat acknowledgement.",
            )
            facts(
                [
                    (
                        "Connection",
                        "Connected (API reported)" if alive else "Offline or unavailable",
                    ),
                    ("Observed profile", live.get("daemon_current_state", "Unknown")),
                    ("Virtual users", live.get("daemon_vus", "Unknown")),
                    ("Heartbeat age (s)", live.get("last_heartbeat_seconds_ago", "Unknown")),
                    ("Window remaining (s)", live.get("daemon_remaining_s", "Unknown")),
                    ("Pending request", live.get("override_state") or "None reported"),
                ]
            )
        if not alive:
            st.warning("Profile requests are disabled until the daemon reports a live connection.")
        feedback = st.empty()
        profiles = (
            ("Steady normal", "STEADY_NORMAL", "4–8 VUs · 20–45 min"),
            ("Rush hour", "BURST_BUSY", "18–28 VUs · 10–20 min"),
            ("Flash sale", "FLASH_ANOMALY", "50–75 VUs · 3–8 min"),
            ("Cooling down", "COOLING_DOWN", "8–14 VUs · 5–10 min"),
            ("Quiet night", "IDLE_SILENT", "0–1 VUs · 5–15 min"),
            (
                "Drift anomaly",
                "DRIFT_ANOMALY",
                "35–55 VUs · unavailable pending backend correction",
            ),
        )
        with st.container(key="operation-profiles"):
            columns = st.columns(2)
            for i, (label, state, note) in enumerate(profiles):
                with columns[i % 2], st.container(key=f"panel-profile-{state.lower()}"):
                    heading(label, "drift" if state == "DRIFT_ANOMALY" else "replicas", note)
                    if live.get("daemon_current_state") == state:
                        st.caption(
                            "Observed profile" if alive else "Last reported profile (offline)"
                        )
                    if st.button(
                        f"Request {label.lower()}",
                        key=f"request_{state}",
                        width="stretch",
                        disabled=not alive or state == "DRIFT_ANOMALY",
                    ):
                        st.session_state.pop("workload_feedback", None)
                        ack = post("/workload/trigger", {"state": state})
                        if ack is not None:
                            if ack.get("status") == "ok" and ack.get("override_state") == state:
                                st.session_state["workload_feedback"] = (
                                    f"Request accepted: {state}. Check the observed profile after the next heartbeat; execution is not yet confirmed."
                                )
                                st.rerun()
                            else:
                                st.error(
                                    "The API did not acknowledge the requested profile. No switch was confirmed."
                                )
        if "workload_feedback" in st.session_state:
            feedback.info(st.session_state["workload_feedback"])
        with st.container(key="panel-lifecycle"):
            heading(
                "Retraining lifecycle",
                "events",
                "Coordinator metadata reported by the API. Completion and model promotion require independent verification.",
            )
            st.warning(
                "Drift injection and lifecycle launch/stop are unavailable. Start/stop routes are absent, and drift orchestration inserts demonstration telemetry and promotion results into shared buffers."
            )
            state = read("/monitoring/autonomous-status")
            facts(
                [
                    (label, state.get(key, "Unknown"))
                    for label, key in (
                        ("Coordinator active", "active"),
                        ("Reported stage", "stage"),
                        ("Reported job", "job_name"),
                    )
                ]
            )
            rows = state.get("timeline", [])
            if isinstance(rows, list):
                table(
                    [
                        {key: row[key] for key in ("timestamp", "stage", "status") if key in row}
                        for row in rows
                        if isinstance(row, dict)
                    ]
                )
            else:
                st.warning("Coordinator timeline is invalid.")

    elif page == "retrain":
        heading(
            "Drift evaluation",
            "drift",
            "PSI compares the API decision buffer against a generated demo/reference distribution, not an immutable training baseline.",
        )
        if st.button("Evaluate telemetry drift (PSI)", width="stretch"):
            st.session_state.pop("drift_result", None)
            result = read("/monitoring/drift")
            if result:
                st.session_state["drift_result"] = result
        result = st.session_state.get("drift_result")
        if result:
            try:
                score = number(result["psi_score"])
                cycles = number(result["evaluated_cycles"])
                threshold = number(result["threshold"])
                if cycles < 3:
                    st.warning(
                        "Insufficient decision samples. The API substitutes demo inputs below three samples; no live drift verdict is available."
                    )
                else:
                    st.metric("Reported PSI (demo reference)", f"{score:.4f}")
                    st.caption(
                        f"{int(cycles)} buffered samples · API threshold {threshold:g}. This score alone does not verify a production drift incident."
                    )
                    features = mapping(result.get("monitored_features"))
                    table(
                        [
                            {"feature": name, **value}
                            for name, value in features.items()
                            if isinstance(value, dict)
                        ]
                    )
            except (KeyError, TypeError, ValueError, OverflowError):
                st.warning("Drift response is incomplete or invalid. No verdict is available.")
        with st.container(key="panel-retraining"):
            heading(
                "Manual retraining",
                "pipeline",
                "Unavailable until the trigger API reports a real job outcome and verified promotion.",
            )
            st.button("Trigger retraining", disabled=True, width="stretch")
            st.warning(
                "The current trigger changes in-memory model metadata and inserts fixed metrics before the Kubernetes job finishes. It cannot confirm training, quality-gate success, or hot reload. Use the operational pipeline outside this dashboard and verify its job and MLflow records."
            )

    elif page == "audit":
        heading(
            "Operation records",
            "events",
            "Source-reported ingestion, model metadata, decisions and scaling actions.",
        )
        st.warning(
            "The inference service contains seeded history and unmarked demonstration rows. These records are not independent proof of ingestion, training, live traffic, or applied scaling."
        )
        audit = read("/operations/audit")
        st.caption(f"API snapshot timestamp: {audit.get('timestamp', 'Unknown')}")
        with st.container(key="panel-ingestion"):
            heading(
                "Ingestion",
                "pipeline",
                "Last reported metadata and ingestion history; no UI fallback batches.",
            )
            st.json(mapping(audit.get("last_ingestion")))
            table(audit.get("ingestion_history", []))
        with st.container(key="panel-retrain-history"):
            heading(
                "Retraining records",
                "model",
                "Verify source claims against job logs and MLflow artifacts.",
            )
            table(mapping(audit.get("retraining")).get("history", []))
        with st.container(key="panel-decisions"):
            heading(
                "Inference decisions",
                "forecast",
                "Recommendations recorded by the scale-decision API; these do not establish applied scaling.",
            )
            scaling = mapping(audit.get("scaling_api"))
            st.caption(
                f"API-reported total: {scaling.get('total_calls_tracked', 'Unknown')} · the service initializes this counter with a seeded value."
            )
            table(scaling.get("recent_decisions", []))
        with st.container(key="panel-actions"):
            heading(
                "Scaling actions",
                "replicas",
                "Action records require the controller's reported outcome; a recommendation is not an applied action.",
            )
            table(mapping(audit.get("scaling_actions")).get("recent_actions", []))

    elif page == "registry":
        heading(
            "Model metadata",
            "model",
            "Serving metadata from health and registry metadata from the audit API.",
        )
        st.warning(
            "Audit history can contain seeded or demonstration metadata. Validate scores, stages and dataset hashes in MLflow and DVC before using them as evidence."
        )
        health = read("/health")
        audit = read("/operations/audit")
        with st.container(key="panel-serving"):
            facts(
                [
                    (label, health.get(key, "Unknown"))
                    for label, key in (
                        ("Model", "model_name"),
                        ("Version", "model_version"),
                        ("Alias", "model_alias"),
                        ("Algorithm", "model_algorithm"),
                        ("Ready (API reported)", "model_ready"),
                    )
                ]
            )
        for label, key in (
            ("Latest reported model", "latest"),
            ("Reported challenger", "challenger"),
        ):
            with st.expander(label):
                st.json(mapping(mapping(audit.get("retraining")).get(key)))
        st.link_button("Open MLflow registry", MLFLOW_URL, width="stretch")
        with st.container(key="panel-lineage"):
            heading(
                "Dataset lineage",
                "pipeline",
                "DVC stores content-addressed blobs in MinIO; the table preserves source filenames and reported counts.",
            )
            table(audit.get("ingestion_history", []))
        with st.expander("Recent API telemetry records"):
            table(read("/telemetry/live-sample", list))

    elif page == "benchmark":
        heading(
            "HPA comparison",
            "replicas",
            "A measured comparison requires baseline and predictive runs under the same workload, with traceable artifacts.",
        )
        st.info(
            "No verified benchmark artifact is connected to this dashboard. The previous fixed reaction-time, latency and success-rate figures have been removed."
        )
        st.markdown("#### Recent API records")
        st.caption(
            "These records may include demonstration inputs. They cannot establish SLO compliance or an HPA advantage."
        )
        table(read("/telemetry/live-sample", list))
        st.link_button("Inspect telemetry in Grafana", GRAFANA_URL, width="stretch")

    elif page == "finops":
        heading(
            "Cost and carbon scenario",
            "replicas",
            "An allocation estimate using your assumptions; this is not a cloud bill or measured emissions inventory.",
        )
        with st.container(key="panel-cost-assumptions"):
            days = st.slider("Evaluation period (days)", 7, 60, 30)
            rate = st.number_input(
                "Assumed vCPU cost ($/hr)", min_value=0.0, value=0.0175, format="%.4f"
            )
            exchange = st.number_input("IDR/USD exchange rate", min_value=1, value=15800, step=100)
            static = st.number_input("Static baseline replicas", min_value=1, value=6)
            reactive = st.number_input(
                "Assumed average HPA replicas", min_value=0.0, value=2.8, step=0.1
            )
            predictive = st.number_input(
                "Assumed average predictive replicas", min_value=0.0, value=1.6, step=0.1
            )
        st.caption(
            "Fixed scenario assumptions: 0.175 vCPU and 0.152 GiB per replica; $0.0022/GiB-hour; 0.0042 kg CO2e/vCPU-hour. These factors are illustrative and are not provider-certified rates. No live replica average is inferred from contaminated decision buffers."
        )
        hours = days * 24
        allocations = [float(static), reactive, predictive]
        costs = [pods * hours * (0.175 * rate + 0.152 * 0.0022) for pods in allocations]
        carbon = [pods * hours * 0.175 * 0.0042 for pods in allocations]
        df = pd.DataFrame(
            {
                "Strategy": ["Static assumption", "HPA assumption", "Predictive assumption"],
                "Estimated cost (IDR)": [cost * exchange for cost in costs],
                "Estimated carbon (kg CO2e)": carbon,
            }
        ).set_index("Strategy")
        with st.container(key="operation-metrics"):
            left, right = st.columns(2)
            left.metric("Estimated predictive cost", f"${costs[2]:.2f}")
            right.metric("Estimated savings vs static", f"${costs[0] - costs[2]:.2f}")
        st.dataframe(df, width="stretch")
        st.bar_chart(df["Estimated cost (IDR)"], color=palette["chart-actual"])
        st.bar_chart(df["Estimated carbon (kg CO2e)"], color=palette["chart-predicted"])

    elif page == "k8s":
        heading(
            "Service topology",
            "replicas",
            "Configured architecture from the operational handoff; this diagram is not a live Kubernetes inventory.",
        )
        st.code(
            """AWS K3s: control-plane · worker-1 · worker-2
  titipin
    laravel-backend       Target application
    MinIO                Dataset object storage
  monitoring
    Prometheus           Telemetry collection
    Grafana              Observability
  mlops
    inference-api        Model serving
    predictive-scaler    Replica control loop
    mlops-dashboard      This console
    mlops-mlflow         Model registry
    training CronJob     Scheduled training pipeline""",
            language="text",
        )
        st.caption(
            "Node health, ready-pod counts and placement require cluster inspection. Connected services are available in the sidebar."
        )


if page not in ("overview", "sim"):
    operational_view()

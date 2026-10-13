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
from adapter import normalize_decisions, number, read_resource, runtime_policy
from cluster import render_cluster
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
    can_auto_refresh = page in (
        "overview",
        "injector",
        "audit",
        "registry",
        "benchmark",
        "finops",
        "k8s",
        "retrain",
    )
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
    token = st.session_state.get("operator_token")
    if not token:
        st.error("Unlock operator access in the sidebar before sending a request.")
        return None
    try:
        response = requests.post(
            f"{INFERENCE_API_URL.rstrip('/')}{path}",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if response.status_code in (401, 403):
            lock_operator()
            st.session_state["operator_notice"] = (
                "Operator access expired or was rejected. Unlock access again."
            )
            st.rerun()
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


def lock_operator():
    st.session_state.pop("operator_token", None)
    st.session_state.pop("operator_token_input", None)


if page in ("sim", "retrain", "injector"):
    with (
        st.sidebar,
        st.expander("Operator access", expanded=not st.session_state.get("operator_token")),
    ):
        if st.session_state.get("operator_token"):
            st.caption("Operator access unlocked for this session.")
            st.button("Lock operator access", on_click=lock_operator)
        else:
            st.text_input("Operator token", type="password", key="operator_token_input")
            if st.button("Unlock operator access"):
                candidate = st.session_state.get("operator_token_input", "").strip()
                try:
                    response = requests.post(
                        f"{INFERENCE_API_URL.rstrip('/')}/auth/operator",
                        json={},
                        headers={"Authorization": f"Bearer {candidate}"},
                        timeout=5,
                    )
                    response.raise_for_status()
                    if response.json().get("authenticated") is not True:
                        raise ValueError()
                    st.session_state["operator_token"] = candidate
                    st.rerun()
                except (requests.RequestException, ValueError, TypeError):
                    st.error("Access was not unlocked. Check the token or service availability.")
            st.caption("Read-only views stay public. Tokens are never shared with the cluster map.")

operator_ready = bool(st.session_state.get("operator_token"))
if notice := st.session_state.pop("operator_notice", None):
    st.warning(notice)
if page in ("sim", "retrain", "injector") and not operator_ready:
    st.info("Read-only mode. Unlock Operator access in the sidebar to use write controls.")


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
        if st.button(
            "Compute forecast", type="primary", width="stretch", disabled=not operator_ready
        ):
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


def lifecycle(state):
    try:
        progress = min(100.0, number(state.get("progress_pct", 0))) / 100
    except (ValueError, TypeError):
        progress = 0.0
    st.progress(progress)
    facts(
        [
            ("Stage", f"{state.get('stage_index', 0)}/5 · {state.get('stage_title', 'Standby')}"),
            ("Kubernetes job", state.get("job_name") or "Not dispatched"),
            ("Active model", state.get("champion_version") or "Unknown"),
            (
                "Elapsed",
                f"{state['elapsed_seconds']} s"
                if state.get("elapsed_seconds") is not None
                else "End time not recorded",
            ),
        ]
    )
    if state.get("stage") == "COMPLETED":
        st.success(
            f"Retraining completed. Model {state.get('champion_version')} is loaded; job {state.get('job_name')} succeeded."
        )
        cols = st.columns(3)
        metrics = mapping(state.get("metrics"))
        mae = metrics.get("candidate_holdout_mae", metrics.get("val_mae"))
        cols[0].metric(
            "Champion model",
            str(state.get("champion_version", "Unknown")),
            help=f"Candidate holdout MAE: {mae} RPS",
        )
        cols[1].metric("Quality gate", str(state.get("quality_gate", "Unknown")))
        cols[2].metric("Hot reload", str(state.get("hot_reload", "Unknown")))
    elif state.get("stage") == "FAILED":
        st.error(state.get("error", "Lifecycle failed; inspect the Kubernetes job logs."))
    elif state.get("active"):
        st.info(
            "Lifecycle running. Job and model outcomes update from the backend; keep Auto-refresh enabled."
        )
    rows = state.get("timeline", [])
    if isinstance(rows, list) and rows:
        table(
            [
                {key: row.get(key) for key in ("timestamp", "stage", "title", "status")}
                for row in rows
                if isinstance(row, dict)
            ]
        )
    with st.expander("Persisted lifecycle history"):
        history = read("/operations/history")
        if history.get("persistent"):
            table(
                [
                    {
                        key: item.get(key)
                        for key in (
                            "operation_id",
                            "stage",
                            "started_at",
                            "finished_at",
                            "champion_version",
                        )
                    }
                    for item in history.get("operations", [])
                    if isinstance(item, dict)
                ]
            )
        else:
            st.caption("Persistent history is unavailable on this source.")


@st.fragment(run_every=interval)
def operational_view():
    if page == "injector":
        heading(
            "Traffic profiles",
            "pipeline",
            "Control the remote k6 generator and follow the five-phase training lifecycle.",
        )
        live = read("/workload/status")
        alive = live.get("daemon_alive") is True
        with st.container(key="panel-daemon"):
            heading(
                "Generator status",
                "health",
                "Observed profile and pending request are separate until the next heartbeat.",
            )
            facts(
                [
                    ("Connection", "Connected" if alive else "Offline or unavailable"),
                    ("Observed profile", live.get("daemon_current_state", "Unknown")),
                    ("Virtual users", live.get("daemon_vus", "Unknown")),
                    ("Heartbeat age (s)", live.get("last_heartbeat_seconds_ago", "Unknown")),
                    ("Window remaining (s)", live.get("daemon_remaining_s", "Unknown")),
                    ("Pending request", live.get("override_state") or "None"),
                ]
            )
        if not alive:
            st.info(
                "The daemon is offline. Requests become available after its next live heartbeat."
            )
        feedback = st.empty()
        profiles = (
            ("Steady normal", "STEADY_NORMAL", "4–8 VUs · 20–45 min"),
            ("Rush hour", "BURST_BUSY", "18–28 VUs · 10–20 min"),
            ("Flash sale", "FLASH_ANOMALY", "50–75 VUs · 3–8 min"),
            ("Cooling down", "COOLING_DOWN", "8–14 VUs · 5–10 min"),
            ("Quiet night", "IDLE_SILENT", "0–1 VUs · 5–15 min"),
            ("Drift anomaly", "DRIFT_ANOMALY", "35–55 VUs · High payload & memory drift anomaly"),
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
                        disabled=not alive or not operator_ready,
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
                "Autonomous retraining lifecycle",
                "events",
                "Traffic injection → drift evaluation → Kubernetes training → registry verification → serving reload.",
            )
            state = read("/monitoring/autonomous-status")
            if state.get("active"):
                if st.button("Stop Running Scenario", width="stretch", disabled=not operator_ready):
                    result = post("/monitoring/autonomous-scenario/stop", {})
                    if result and result.get("status") == "ok":
                        st.session_state["lifecycle_notice"] = (
                            "Stop requested. Traffic is returning to the steady baseline."
                        )
                        st.rerun()
            elif st.button(
                "Launch Autonomous Lifecycle Simulation",
                type="primary",
                width="stretch",
                disabled=not alive or not operator_ready,
            ):
                result = post("/monitoring/autonomous-scenario/start", {})
                if result and result.get("status") == "ACCEPTED":
                    st.session_state["lifecycle_notice"] = (
                        f"Lifecycle accepted: {result.get('operation_id')}."
                    )
                    st.rerun()
            if st.session_state.get("lifecycle_notice"):
                st.caption(st.session_state["lifecycle_notice"])
            lifecycle(state)

    elif page == "retrain":
        heading(
            "Drift and continuous training",
            "drift",
            "Compare buffered live telemetry with the configured reference CSV, then run the training pipeline.",
        )
        if st.button("Evaluate telemetry drift (PSI)", width="stretch"):
            st.session_state.pop("drift_result", None)
            result = read("/monitoring/drift")
            if result:
                st.session_state["drift_result"] = result
        result = st.session_state.get("drift_result")
        if result:
            try:
                score, threshold = number(result["psi_score"]), number(result["threshold"])
                if number(result["evaluated_cycles"]) < 3:
                    raise ValueError()
                st.metric("Overall PSI", f"{score:.4f}")
                if score >= threshold:
                    st.warning(f"Drift detected: PSI {score:.4f} ≥ {threshold:g}.")
                else:
                    st.success(f"Stable distribution: PSI {score:.4f} < {threshold:g}.")
                st.caption(
                    f"Reference: {result.get('reference', 'configured CSV')} · {result['evaluated_cycles']} live samples"
                )
                table(
                    [
                        {
                            "Feature": name,
                            "PSI score": value.get("psi"),
                            "Live mean": value.get("live_mean"),
                            "Baseline mean": value.get("baseline_mean"),
                            "Status": "DRIFT" if value.get("has_drift") else "STABLE",
                        }
                        for name, value in mapping(result.get("monitored_features")).items()
                        if isinstance(value, dict)
                    ]
                )
            except (KeyError, TypeError, ValueError, OverflowError):
                st.info(
                    f"Drift evaluation is waiting for samples/reference: {result.get('status', 'Incomplete response')}."
                )
        with st.container(key="panel-retraining"):
            heading(
                "Event-driven retraining",
                "pipeline",
                "Dispatch a real training job. Completion follows the job result, validation gate and verified model reload.",
            )
            if st.button(
                "Trigger Event-Driven Retraining Pipeline",
                type="primary",
                width="stretch",
                disabled=not operator_ready,
            ):
                st.session_state.pop("retrain_notice", None)
                result = post("/monitoring/retrain/trigger", {})
                if result and result.get("status") == "ACCEPTED":
                    st.session_state["retrain_notice"] = (
                        f"Training accepted: {result.get('operation_id')}."
                    )
            if st.session_state.get("retrain_notice"):
                st.caption(st.session_state["retrain_notice"])
            lifecycle(read("/monitoring/autonomous-status"))

    elif page == "audit":
        heading(
            "Operation records",
            "events",
            "Live ingestion lineage, registry history, decisions and applied scaling events.",
        )
        audit = read("/operations/audit")
        st.caption(
            f"API snapshot: {audit.get('timestamp', 'Unknown')} · registry refresh: {audit.get('registry_updated_at', 'Unknown')}"
        )
        with st.container(key="panel-ingestion"):
            heading(
                "Data ingestion and CAS lineage",
                "pipeline",
                "MinIO metadata and verified content-addressed objects.",
            )
            table(audit.get("ingestion_history", []))
        with st.container(key="panel-retrain-history"):
            heading(
                "Retraining history",
                "model",
                "Version, algorithm, validation result and registry stage.",
            )
            rows = mapping(audit.get("retraining")).get("history", [])
            table(
                [
                    {
                        k: row.get(k)
                        for k in ("version", "timestamp", "algorithm", "val_mae", "stage", "run_id")
                    }
                    for row in rows
                    if isinstance(row, dict)
                ]
                if isinstance(rows, list)
                else rows
            )
        with st.container(key="panel-decisions"):
            heading(
                "Inference decisions",
                "forecast",
                "Recent controller observations and recommendations.",
            )
            scaling = mapping(audit.get("scaling_api"))
            st.caption(
                f"Tracked evaluations since service start: {scaling.get('total_calls_tracked', 'Unknown')}"
            )
            table(scaling.get("recent_decisions", []))
        with st.container(key="panel-actions"):
            heading(
                "Applied scaling actions",
                "replicas",
                "Actions reported after a successful Kubernetes scale patch.",
            )
            table(mapping(audit.get("scaling_actions")).get("recent_actions", []))

    elif page == "registry":
        heading(
            "Champion and challenger",
            "model",
            "Registry aliases and validation metadata, with the currently loaded serving version.",
        )
        health, audit = read("/health"), read("/operations/audit")
        with st.container(key="operation-profiles"):
            columns = st.columns(2)
            for column, label, key in (
                (columns[0], "Champion · Production", "latest"),
                (columns[1], "Challenger · Staging", "challenger"),
            ):
                model = mapping(mapping(audit.get("retraining")).get(key))
                with column, st.container(key=f"panel-model-{key}"):
                    heading(label, "model", f"@{'champion' if key == 'latest' else 'challenger'}")
                    facts(
                        [
                            ("Version", model.get("version", "Unknown")),
                            ("Algorithm", model.get("algorithm", "Unknown")),
                            ("Validation MAE", model.get("val_mae") or "Unknown"),
                            ("Registry stage", model.get("stage", "Unknown")),
                        ]
                    )
                    if key == "latest":
                        st.caption(
                            f"Serving: {health.get('model_version', 'Unknown')} · {'Ready' if health.get('model_ready') else 'Unavailable'}"
                        )
        st.link_button("Open MLflow registry", MLFLOW_URL, width="stretch")
        with st.container(key="panel-lineage"):
            heading(
                "DVC content-addressable storage",
                "pipeline",
                "Batch, processed/raw dataset, actual row count and MinIO CAS hash.",
            )
            table(audit.get("ingestion_history", []))
        with st.expander("Recent API telemetry records"):
            table(read("/telemetry/live-sample", list))

    elif page == "benchmark":
        heading(
            "HPA vs predictive benchmark",
            "replicas",
            "65-VU reference experiment and an independently refreshed production SLO snapshot.",
        )
        bench = json.loads((ASSETS / "benchmark-reference.json").read_text())
        st.caption(
            f"Reference source: {bench['source']}. These reference results are separate from the live cards below."
        )
        table(bench["rows"])
        samples = read("/telemetry/live-sample", list)
        valid, _ = normalize_decisions(samples)
        with st.container(key="operation-metrics"):
            cols = st.columns(4)
            sample = valid[-1] if valid else None
            cols[0].metric(
                "Live ingress workload", f"{sample['actual_rps']:.1f} RPS" if sample else "Unknown"
            )
            cols[1].metric(
                "Live P95 latency",
                f"{sample['p95_latency_ms']:.1f} ms" if sample else "Unknown",
                delta=("SLO MET (<100 ms)" if sample["p95_latency_ms"] < 100 else "SLO ELEVATED")
                if sample
                else None,
            )
            cols[2].metric(
                "Active replicas",
                sample["observed_replicas"] if sample else "Unknown",
                delta=f"Target: {sample['recommended_replicas']}" if sample else None,
            )
            cols[3].metric(
                "Forecast (+60s)", f"{sample['forecast_rps']:.1f} RPS" if sample else "Unknown"
            )
        if sample:
            st.caption(
                f"Live snapshot observed at {sample['issued_at_utc'].isoformat()}; this is a point observation, not a window-wide compliance statistic."
            )
        table(samples)
        st.link_button("Inspect telemetry in Grafana", GRAFANA_URL, width="stretch")

    elif page == "finops":
        heading(
            "Live allocation cost and carbon",
            "replicas",
            "Cost estimates update with the controller's recent replica recommendations.",
        )
        decisions, _ = normalize_decisions(read("/scaling/decisions", list))
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
        predictive = (
            sum(row["recommended_replicas"] for row in decisions) / len(decisions)
            if decisions
            else 1.6
        )
        if decisions:
            observed = sum(row["observed_replicas"] for row in decisions) / len(decisions)
            st.caption(
                f"Dynamic allocation coefficient: {predictive:.2f} recommended replicas from {len(decisions)} decisions · observed mean {observed:.2f} replicas."
            )
        else:
            st.info(
                "Waiting for live decisions. The cost preview uses a disclosed default of 1.6 replicas until observations arrive."
            )
        st.caption(
            "Estimates use 0.175 vCPU and 0.152 GiB per replica, $0.0022/GiB-hour and an illustrative 0.0042 kg CO2e/vCPU-hour factor. Cloud bills and measured emissions are not connected."
        )
        hours = days * 24
        costs = [
            pods * hours * (0.175 * rate + 0.152 * 0.0022)
            for pods in (static, reactive, predictive)
        ]
        carbon = [pods * hours * 0.175 * 0.0042 for pods in (static, reactive, predictive)]
        saved = costs[0] - costs[2]
        with st.container(key="operation-metrics"):
            cols = st.columns(4)
            cols[0].metric(
                "Estimated cost saved",
                f"Rp {saved * exchange:,.0f}",
                delta=f"{saved / costs[0] * 100:.1f}% vs static" if costs[0] else None,
            )
            cols[1].metric("Estimated cloud cost", f"${costs[2]:.2f}")
            cols[2].metric("Estimated carbon", f"{carbon[2]:.2f} kg CO2e")
            cols[3].metric(
                "Allocation efficiency",
                f"{(static - predictive) / static * 100:.1f}%",
                delta=f"{predictive:.2f} mean replicas",
            )
        df = pd.DataFrame(
            {
                "Strategy": ["Static baseline", "HPA assumption", "Predictive recommendation"],
                "Estimated cost (IDR)": [cost * exchange for cost in costs],
                "Estimated carbon (kg CO2e)": carbon,
            }
        ).set_index("Strategy")
        st.dataframe(df, width="stretch")
        st.bar_chart(df["Estimated cost (IDR)"], color=palette["chart-actual"])
        st.bar_chart(df["Estimated carbon (kg CO2e)"], color=palette["chart-predicted"])

    elif page == "k8s":
        heading(
            "Cluster topology",
            "replicas",
            "Select a node, workload or system component to inspect its role and operational evidence.",
        )
        health, cluster = read("/health"), read("/cluster/status")
        with st.container(key="operation-metrics"):
            cols = st.columns(3)
            cols[0].metric(
                "Serving engine", "HEALTHY" if health.get("model_ready") else "UNAVAILABLE"
            )
            cols[1].metric("Active model", str(health.get("model_version", "Unknown")))
            cols[2].metric("Predictive loop", str(health.get("predictive_loop", "Unknown")))
        render_cluster(
            cluster,
            health,
            read("/workload/status"),
            palette,
            {
                "dashboard": "https://mlops.titipin.me",
                "inference": PUBLIC_INFERENCE_DOCS,
                "api": API_URL,
                "mlflow": MLFLOW_URL,
                "grafana": GRAFANA_URL,
                "minio": MINIO_URL,
            },
        )
        with st.expander("Inspect pod inventory as a table"):
            table(
                [
                    {
                        "Component": p.get("name"),
                        "Namespace": p.get("namespace"),
                        "Node": p.get("node"),
                        "Ready": f"{p.get('ready', 0)}/{p.get('containers', 0)}",
                        "Phase": p.get("phase"),
                    }
                    for p in cluster.get("pods", [])
                    if isinstance(p, dict)
                ]
            )


if page not in ("overview", "sim"):
    operational_view()

#!/usr/bin/env python3
"""
Predictive Autoscaler Inference Service (FastAPI)
=================================================
Menyediakan REST API endpoint inferensi model pembelajaran mesin (Random Forest / LightGBM)
yang dimuat dari MLflow Model Registry ('@champion'). Menghasilkan estimasi trafik beban
kerja (RPS) 60 detik ke depan dan rekomendasi replika pod Kubernetes (1-4 pod).

Endpoints:
  - GET  /health          : Status kesehatan servis dan metadata model aktif
  - GET  /metrics         : Metrik Prometheus untuk observabilitas model serving
  - POST /predict         : Inferensi beban trafik dan rekomendasi kapasitas pod
  - POST /scale-decision  : Keputusan penskalaan terstruktur untuk kontroler K8s
"""

import json
import logging
import math
import os
import ssl
import subprocess
import threading
import time
import urllib.request
from collections import deque
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import mlflow
import mlflow.pyfunc
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, Field

os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"
logger = logging.getLogger("predictive-autoscaler")

# ---------------------------------------------------------------------------
# Configuration & Constants
# ---------------------------------------------------------------------------
MODEL_NAME = os.getenv("MODEL_NAME", "predictive-autoscaler")
MODEL_ALIAS = os.getenv("MODEL_ALIAS", "champion")
DEFAULT_TRACKING_URI = os.getenv(
    "MLFLOW_TRACKING_URI",
    "http://mlops-mlflow-svc:5000"
    if (os.getenv("KUBERNETES_SERVICE_HOST") or os.path.exists("/var/run/secrets/kubernetes.io"))
    else "sqlite:///mlflow.db",
)
TARGET_RPS_PER_POD = float(os.getenv("TARGET_RPS_PER_POD", "10.0"))
MIN_REPLICAS = int(os.getenv("MIN_REPLICAS", "1"))
MAX_REPLICAS = int(os.getenv("MAX_REPLICAS", "6"))


# Prometheus Metrics
REQUESTS_TOTAL = Counter(
    "autoscaler_inference_requests_total",
    "Total requests to inference endpoints",
    ["endpoint", "status"],
)
INFERENCE_LATENCY = Histogram(
    "autoscaler_inference_latency_seconds",
    "Inference latency in seconds",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)
PREDICTED_RPS_GAUGE = Gauge(
    "autoscaler_predicted_workload_rps",
    "Latest predicted request rate (RPS) for t+60s",
)
RECOMMENDED_REPLICAS_GAUGE = Gauge(
    "autoscaler_recommended_replicas",
    "Latest recommended pod replicas count",
)

# Global model container
model_store: Dict[str, Any] = {
    "model": None,
    "model_uri": f"models:/{MODEL_NAME}@{MODEL_ALIAS}",
    "loaded_at": None,
    "load_time_ms": 0.0,
    "version": "Unknown",
    "model_algorithm": "Unknown",
}

total_evaluations_count: int = 0


def find_local_model_artifact() -> Optional[str]:
    """Mencari path direktori artefak champion model secara lokal di file system."""
    base_dirs = [Path("."), Path("/app"), Path(__file__).resolve().parent.parent.parent]
    champion_run_id = None
    for b in base_dirs:
        meta_file = b / "models" / "champion_model_metadata.json"
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    champion_run_id = data.get("champion_run_id")
                    if champion_run_id:
                        break
            except Exception:
                continue

    # 1. Exact match by champion_run_id
    if champion_run_id:
        for b in base_dirs:
            if not b.exists():
                continue
            for p in b.glob("mlruns/**/MLmodel"):
                try:
                    content = p.read_text(encoding="utf-8")
                    if f"run_id: {champion_run_id}" in content:
                        return str(p.parent.resolve())
                except Exception:
                    continue

    # 2. Generic scikit-learn fallback
    for b in base_dirs:
        if not b.exists():
            continue
        for p in b.glob("mlruns/**/MLmodel"):
            try:
                content = p.read_text(encoding="utf-8")
                if "flavors:" in content and "sklearn" in content:
                    return str(p.parent.resolve())
            except Exception:
                continue
    return None


def load_model_from_registry(strict: bool = False) -> bool:
    """Load an exact registry version before atomically replacing the serving model."""
    from mlflow.tracking import MlflowClient

    mlflow.set_tracking_uri(DEFAULT_TRACKING_URI)
    t0 = time.perf_counter()
    try:
        client = MlflowClient(DEFAULT_TRACKING_URI)
        version = client.get_model_version_by_alias(MODEL_NAME, MODEL_ALIAS)
        uri = f"models:/{MODEL_NAME}/{version.version}"
        loaded = mlflow.pyfunc.load_model(uri)
        run = client.get_run(version.run_id)
        model_store.update(
            model=loaded,
            model_uri=uri,
            version=f"v{version.version}",
            model_algorithm=run.data.params.get("model_type", "Unknown"),
            loaded_at=datetime.now(timezone.utc).isoformat(),
            load_time_ms=round((time.perf_counter() - t0) * 1000, 2),
        )
        return True
    except Exception:
        logger.warning("Registry load failed; retaining the currently serving model.")
        if not strict and model_store.get("model") is None:
            local = find_local_model_artifact()
            if local:
                try:
                    loaded = mlflow.pyfunc.load_model(local)
                    model_store.update(
                        model=loaded,
                        model_uri=f"file://{local}",
                        version="local",
                        loaded_at=datetime.now(timezone.utc).isoformat(),
                    )
                    return True
                except Exception:
                    logger.warning("Local model artifact could not be loaded.")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle startup: load ML model into memory."""
    load_model_from_registry()
    stop_sync = threading.Event()

    def refresh_metadata():
        while not stop_sync.is_set():
            _sync_live_ingestion_and_mlflow(force=True)
            stop_sync.wait(15)

    threading.Thread(target=refresh_metadata, daemon=True).start()
    yield
    stop_sync.set()
    scenario_cancel.set()


app = FastAPI(
    title="Predictive Horizontal Pod Autoscaler API",
    description="ML-driven workload forecast and replica recommendation service for Kubernetes k3s.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------
class TelemetryFeatures(BaseModel):
    request_rate: float = Field(default=10.0, description="Current workload request rate (RPS)")
    php_cpu_cores: float = Field(default=0.25, description="CPU usage in cores")
    p95_latency_seconds: float = Field(default=0.035, description="P95 request latency in seconds")
    php_memory_mb: float = Field(default=110.0, description="PHP-FPM memory footprint in MB")
    rps_lag1: Optional[float] = Field(default=None, description="Lag 1 RPS (-15s)")
    rps_lag2: Optional[float] = Field(default=None, description="Lag 2 RPS (-30s)")
    cpu_lag1: Optional[float] = Field(default=None, description="Lag 1 CPU cores")
    cpu_lag2: Optional[float] = Field(default=None, description="Lag 2 CPU cores")
    rps_roll_mean_30s: Optional[float] = Field(default=None, description="Rolling mean RPS 30s")
    rps_roll_mean_60s: Optional[float] = Field(default=None, description="Rolling mean RPS 60s")
    rps_roll_std_60s: Optional[float] = Field(default=None, description="Rolling std RPS 60s")
    rps_delta: Optional[float] = Field(default=None, description="RPS derivative delta")
    cpu_delta: Optional[float] = Field(default=None, description="CPU derivative delta")
    hour: Optional[int] = Field(default=None, description="Current hour (0-23)")
    minute: Optional[int] = Field(default=None, description="Current minute (0-59)")
    current_replicas: Optional[int] = Field(default=1, description="Current replica count")


class PredictionResponse(BaseModel):
    model_name: str
    model_version: str
    status: str
    current_workload_rps: float
    predicted_workload_rps_60s: float
    recommended_replicas: int
    target_capacity_rps: float
    scaling_action: str
    inference_latency_ms: float
    timestamp: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health_check() -> Dict[str, Any]:
    """Health check endpoint validating model readiness."""
    is_ready = model_store.get("model") is not None
    active_v = str(model_store.get("version", "Unknown"))
    if active_v.isdigit():
        active_v = f"v{active_v}"
    algo_name = model_store.get("model_algorithm", "Unknown")

    return {
        "status": "healthy" if is_ready else "degraded",
        "service": "predictive-autoscaler-inference",
        "model_ready": is_ready,
        "model_name": MODEL_NAME,
        "model_alias": MODEL_ALIAS,
        "model_version": active_v,
        "model_algorithm": algo_name,
        "model_uri": model_store.get("model_uri"),
        "load_time_ms": model_store.get("load_time_ms"),
        "target_rps_per_pod": TARGET_RPS_PER_POD,
        "replica_bounds": {"min": MIN_REPLICAS, "max": MAX_REPLICAS},
        "total_api_calls": total_evaluations_count,
        "provenance": "live-services",
        "predictive_loop": "ACTIVE"
        if scaling_decisions_ring
        and time.time()
        - datetime.fromisoformat(
            scaling_decisions_ring[0]["timestamp"].replace("Z", "+00:00")
        ).timestamp()
        < 45
        else "WAITING",
        "last_scaling_observation": scaling_decisions_ring[0]["timestamp"]
        if scaling_decisions_ring
        else None,
    }


@app.post("/model/reload")
def reload_model_endpoint() -> Dict[str, Any]:
    """Reloads the champion model dynamically from MLflow Model Registry."""
    reloaded = load_model_from_registry(strict=True)
    is_ready = model_store.get("model") is not None
    return {
        "status": "reloaded" if reloaded else "failed",
        "model_ready": is_ready,
        "model_name": MODEL_NAME,
        "model_alias": MODEL_ALIAS,
        "model_uri": model_store.get("model_uri"),
        "loaded_at": model_store.get("loaded_at"),
        "load_time_ms": model_store.get("load_time_ms"),
    }


@app.get("/metrics")
def prometheus_metrics():
    """Prometheus exposition format for autoscaler telemetry."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/predict", response_model=PredictionResponse)
def predict_workload(payload: TelemetryFeatures):
    """Predict future workload rate and recommend replica count."""
    model = model_store.get("model")
    if model is None:
        REQUESTS_TOTAL.labels(endpoint="/predict", status="error").inc()
        raise HTTPException(
            status_code=503,
            detail="Model belum dimuat ke memory. Periksa MLflow Model Registry.",
        )

    # Impute default lags if not explicitly provided
    req_rate = payload.request_rate
    cpu = payload.php_cpu_cores
    now_struct = time.gmtime()
    hour = int(payload.hour if payload.hour is not None else now_struct.tm_hour)
    minute = int(payload.minute if payload.minute is not None else now_struct.tm_min)

    feature_dict = {
        "request_rate": float(req_rate),
        "php_cpu_cores": float(cpu),
        "p95_latency_seconds": float(payload.p95_latency_seconds),
        "php_memory_mb": float(payload.php_memory_mb),
        "rps_lag1": float(payload.rps_lag1 if payload.rps_lag1 is not None else req_rate),
        "rps_lag2": float(payload.rps_lag2 if payload.rps_lag2 is not None else req_rate),
        "cpu_lag1": float(payload.cpu_lag1 if payload.cpu_lag1 is not None else cpu),
        "cpu_lag2": float(payload.cpu_lag2 if payload.cpu_lag2 is not None else cpu),
        "rps_roll_mean_30s": float(
            payload.rps_roll_mean_30s if payload.rps_roll_mean_30s is not None else req_rate
        ),
        "rps_roll_mean_60s": float(
            payload.rps_roll_mean_60s if payload.rps_roll_mean_60s is not None else req_rate
        ),
        "rps_roll_std_60s": float(
            payload.rps_roll_std_60s if payload.rps_roll_std_60s is not None else 0.0
        ),
        "rps_delta": float(payload.rps_delta if payload.rps_delta is not None else 0.0),
        "cpu_delta": float(payload.cpu_delta if payload.cpu_delta is not None else 0.0),
        "hour": hour,
        "minute": minute,
    }

    df_input = pd.DataFrame([feature_dict])
    if hasattr(model, "metadata") and model.metadata and model.metadata.get_input_schema():
        for col in model.metadata.get_input_schema().inputs:
            t_str = str(col.type).lower()
            if col.name in df_input.columns:
                if "int" in t_str or "long" in t_str:
                    df_input[col.name] = df_input[col.name].round().astype("int64")
                elif "float" in t_str or "double" in t_str:
                    df_input[col.name] = df_input[col.name].astype("float64")

    t0 = time.perf_counter()
    with INFERENCE_LATENCY.time():
        raw_pred = model.predict(df_input)
    latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    pred_val = float(raw_pred[0]) if hasattr(raw_pred, "__getitem__") else float(raw_pred)
    predicted_rps = max(0.0, round(pred_val, 2))

    # MLOps Extrapolation & Safety Guard for Tree Ensemble Models:
    # Tree models (Random Forest) cannot extrapolate above the max target seen in training data (~19.1 RPS).
    # When active workload or positive trend spikes above the training envelope, blend with trend forecast
    # to ensure real-time spike workloads (e.g. 35+ RPS) recommend 3 or 4 replicas to prevent degradation.
    delta = float(payload.rps_delta if payload.rps_delta is not None else 0.0)
    if req_rate > 15.0:
        trend_forecast = req_rate * (1.0 + max(0.05, delta * 0.5))
        predicted_rps = max(predicted_rps, round(trend_forecast, 2))
    elif req_rate > 0.0 and predicted_rps < (req_rate * 0.5):
        predicted_rps = max(predicted_rps, round(req_rate * 0.9, 2))

    # Calculate recommended replicas
    raw_replicas = math.ceil(predicted_rps / TARGET_RPS_PER_POD) if predicted_rps > 0 else 1
    recommended_replicas = max(MIN_REPLICAS, min(MAX_REPLICAS, raw_replicas))

    # Scaling action directive
    if recommended_replicas > 1 and predicted_rps > (req_rate * 1.2):
        action = "SCALE_UP_ANTICIPATORY"
    elif recommended_replicas < 2 and predicted_rps < 4.0:
        action = "SCALE_DOWN_CONSERVATIVE"
    else:
        action = "MAINTAIN_CAPACITY"

    # Update Prometheus metrics
    REQUESTS_TOTAL.labels(endpoint="/predict", status="success").inc()
    PREDICTED_RPS_GAUGE.set(predicted_rps)
    RECOMMENDED_REPLICAS_GAUGE.set(recommended_replicas)

    return PredictionResponse(
        model_name=MODEL_NAME,
        model_version=str(model_store.get("version", "Unknown")),
        status="SUCCESS",
        current_workload_rps=req_rate,
        predicted_workload_rps_60s=predicted_rps,
        recommended_replicas=recommended_replicas,
        target_capacity_rps=recommended_replicas * TARGET_RPS_PER_POD,
        scaling_action=action,
        inference_latency_ms=latency_ms,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )


@app.post("/scale-decision")
def scaling_decision(payload: TelemetryFeatures) -> Dict[str, Any]:
    """Adapter endpoint tailored for Kubernetes Custom HPA Controller."""
    global total_evaluations_count
    total_evaluations_count += 1
    if payload.rps_roll_mean_60s is None:
        recent = [r["input_rps"] for r in list(scaling_decisions_ring)[:3]]
        payload.rps_roll_mean_60s = float(np.mean([payload.request_rate, *recent]))
    pred_res = predict_workload(payload)
    current_reps = int(
        payload.current_replicas or math.ceil(payload.request_rate / TARGET_RPS_PER_POD) or 1
    )

    # Track decision in ring buffer
    scaling_decisions_ring.appendleft(
        {
            "timestamp": pred_res.timestamp,
            "input_rps": round(payload.request_rate, 2),
            "input_cpu": round(payload.php_cpu_cores, 3),
            "input_memory_mb": payload.php_memory_mb,
            "input_rps_roll_mean_60s": payload.rps_roll_mean_60s
            if payload.rps_roll_mean_60s is not None
            else payload.request_rate,
            "source": "predictive-scaler",
            "synthetic": False,
            "input_p95_ms": round((payload.p95_latency_seconds or 0.0) * 1000.0, 1),
            "current_replicas": current_reps,
            "predicted_rps_60s": round(pred_res.predicted_workload_rps_60s, 2),
            "desired_replicas": pred_res.recommended_replicas,
            "action": pred_res.scaling_action,
            "latency_ms": round(pred_res.inference_latency_ms, 2),
        }
    )

    return {
        "kind": "AutoscalingDecision",
        "apiVersion": "autoscaling.titipin.me/v1alpha1",
        "metadata": {
            "targetRef": {"kind": "Deployment", "name": "laravel-backend", "namespace": "titipin"},
            "timestamp": pred_res.timestamp,
        },
        "spec": {
            "currentReplicas": current_reps,
            "desiredReplicas": pred_res.recommended_replicas,
            "predictedRPS": pred_res.predicted_workload_rps_60s,
            "scalingAction": pred_res.scaling_action,
            "policy": {
                "minReplicas": MIN_REPLICAS,
                "maxReplicas": MAX_REPLICAS,
                "targetRPSPerPod": TARGET_RPS_PER_POD,
            },
        },
        "predicted_workload_rps_60s": pred_res.predicted_workload_rps_60s,
        "recommended_replicas": pred_res.recommended_replicas,
        "target_replicas": pred_res.recommended_replicas,
        "desired_replicas": pred_res.recommended_replicas,
        "action": pred_res.scaling_action,
    }


# ---------------------------------------------------------------------------
# Operational Telemetry & Scaling Event Audit Structures
# ---------------------------------------------------------------------------
scaling_decisions_ring: deque = deque(maxlen=60)
scaling_actions_ring: deque = deque(maxlen=40)


@app.post("/scaling/action-record")
def record_scaling_action(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Records an executed scaling event from the predictive scaler daemon."""
    action_item = {
        "timestamp": payload.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        "action": payload.get("action", "SCALE_UP"),
        "from_replicas": int(payload.get("from_replicas", 1)),
        "to_replicas": int(payload.get("to_replicas", 1)),
        "predicted_rps": float(payload.get("predicted_rps", 0.0)),
        "reason": str(payload.get("reason", "Proactive workload demand")),
        "status": "APPLIED (K8s Patched)",
    }
    scaling_actions_ring.appendleft(action_item)
    return {"status": "ok", "total_events": len(scaling_actions_ring)}


@app.get("/scaling/actions")
def get_scaling_actions() -> List[Dict[str, Any]]:
    """Returns recent actual scaling actions executed by controller."""
    return list(scaling_actions_ring)


@app.get("/scaling/decisions")
def get_scaling_decisions() -> List[Dict[str, Any]]:
    """Returns recent evaluation decisions from predictive scaler loop."""
    return list(scaling_decisions_ring)


def compute_psi_between(
    expected: np.ndarray, actual: np.ndarray, num_bins: int = 10, epsilon: float = 1e-4
) -> float:
    """Calculates Population Stability Index between two 1D numeric distributions."""
    if len(expected) == 0 or len(actual) == 0:
        return 0.0
    percentiles = np.linspace(0, 100, num_bins + 1)
    bin_edges = np.percentile(expected, percentiles)
    bin_edges = np.unique(bin_edges)
    if len(bin_edges) < 2:
        bin_edges = np.array([float(expected.min()) - 1e-5, float(expected.max()) + 1e-5])
    bin_edges[0] = -np.inf
    bin_edges[-1] = np.inf

    expected_counts, _ = np.histogram(expected, bins=bin_edges)
    actual_counts, _ = np.histogram(actual, bins=bin_edges)

    expected_pct = expected_counts / len(expected) + epsilon
    actual_pct = actual_counts / len(actual) + epsilon
    expected_pct /= expected_pct.sum()
    actual_pct /= actual_pct.sum()

    psi_val = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
    return float(max(0.0, psi_val))


@app.get("/monitoring/drift")
def evaluate_telemetry_drift() -> Dict[str, Any]:
    """Compare observed scaler samples with the configured reference CSV."""
    path = Path(os.getenv("DRIFT_REFERENCE_PATH", "/app/data/processed/metrics_demo_processed.csv"))
    features = {
        "request_rate": "input_rps",
        "php_cpu_cores": "input_cpu",
        "p95_latency_seconds": "input_p95_ms",
        "php_memory_mb": "input_memory_mb",
        "rps_roll_mean_60s": "input_rps_roll_mean_60s",
    }
    rows = list(scaling_decisions_ring)
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "psi_score": None,
        "threshold": 0.2,
        "evaluated_cycles": len(rows),
        "overall_drift_detected": False,
        "status": "WAITING_FOR_SAMPLES",
        "monitored_features": {},
        "reference": path.name,
    }
    if len(rows) < 3:
        return result
    try:
        reference = pd.read_csv(path)
        for name, field in features.items():
            if name not in reference:
                continue
            values = np.array([float(row[field]) for row in rows if row.get(field) is not None])
            if name == "p95_latency_seconds":
                values = values / 1000
            expected = pd.to_numeric(reference[name], errors="coerce").dropna().to_numpy()
            values = values[np.isfinite(values)]
            if len(values) < 3 or len(expected) < 3:
                continue
            psi = round(compute_psi_between(expected, values), 4)
            result["monitored_features"][name] = {
                "psi": psi,
                "live_mean": float(np.mean(values)),
                "baseline_mean": float(np.mean(expected)),
                "has_drift": psi >= 0.2,
            }
        if not result["monitored_features"]:
            result["status"] = "REFERENCE_UNAVAILABLE"
            return result
        result["psi_score"] = max(row["psi"] for row in result["monitored_features"].values())
        result["overall_drift_detected"] = result["psi_score"] >= 0.2
        result["status"] = "DRIFT_DETECTED" if result["overall_drift_detected"] else "STABLE"
        return result
    except (OSError, ValueError, KeyError):
        result["status"] = "REFERENCE_UNAVAILABLE"
        return result


@app.get("/telemetry/live-sample")
def get_live_telemetry_sample() -> List[Dict[str, Any]]:
    """Returns the latest 5 live telemetry evaluations from the ring buffer."""
    return list(scaling_decisions_ring)[:5]


# ---------------------------------------------------------------------------
# Dynamic Ingestion & Retraining Audit Store
# ---------------------------------------------------------------------------
ingestion_store: Dict[str, Any] = {"last_ingestion": {}, "history": []}


@app.post("/operations/record-ingestion")
def record_ingestion_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Records a new ingestion event dynamically from CT pipeline or manual ingest."""
    ts = payload.get("timestamp", time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))
    item = {
        "timestamp": ts,
        "window_minutes": int(payload.get("window_minutes", 15)),
        "records_count": int(payload.get("records_count", 0)),
        "target_dataset": payload.get("target_dataset", "data/processed/latest.csv"),
        "raw_dataset": payload.get("raw_dataset", "data/raw/latest.csv"),
        "md5": payload.get("md5", ""),
        "bucket": payload.get("bucket", "s3://mlops-dvc"),
        "status": payload.get("status", "REPORTED"),
    }
    ingestion_store["last_ingestion"] = item
    batch_name = f"ING-{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}"
    ingestion_store["history"].insert(
        0,
        {
            "batch": batch_name,
            "time_utc": ts,
            "source": payload.get("source", "API report"),
            "records": item["records_count"],
            "window": f"{item['window_minutes']} min",
            "output": Path(item["target_dataset"]).name,
            "status": item["status"],
        },
    )
    return {"status": "ok", "recorded_batch": batch_name}


retraining_history: List[Dict[str, Any]] = []
registry_snapshot: Dict[str, Any] = {}
_last_live_sync_time = 0.0


def _sync_live_ingestion_and_mlflow(force: bool = False):
    """Refresh metadata off the request path; never relabel the loaded model."""
    global _last_live_sync_time
    if not force and time.time() - _last_live_sync_time < 15:
        return
    _last_live_sync_time = time.time()
    try:
        from src.data.minio_sync import get_minio_client

        client, bucket = get_minio_client()
        objects = [
            o
            for o in client.list_objects(bucket, prefix="processed/")
            if o.object_name.endswith(".csv") and not o.object_name.endswith("latest.csv")
        ]
        objects.sort(key=lambda o: o.last_modified, reverse=True)
        history = []
        for obj in objects[:20]:
            stat = client.stat_object(bucket, obj.object_name)
            meta = stat.metadata or {}
            md5 = meta.get("x-amz-meta-md5", obj.etag)
            cas_key = f"files/md5/{md5[:2]}/{md5[2:]}"
            try:
                client.stat_object(bucket, cas_key)
                synced = True
            except Exception:
                synced = False
            history.append(
                {
                    "batch": obj.object_name,
                    "time_utc": obj.last_modified.isoformat(),
                    "output": obj.object_name,
                    "raw_dataset": meta.get("x-amz-meta-raw-dataset"),
                    "records": int(meta["x-amz-meta-records"])
                    if meta.get("x-amz-meta-records")
                    else None,
                    "md5": md5,
                    "bucket": f"s3://{bucket}",
                    "cas_key": cas_key,
                    "status": "DVC CAS synced" if synced else "Object available",
                    "size": obj.size,
                }
            )
        if history:
            latest = {
                **history[0],
                "records_count": history[0]["records"],
                "timestamp": history[0]["time_utc"],
            }
            ingestion_store.update(history=history, last_ingestion=latest)
    except Exception:
        logger.warning("Dataset metadata refresh unavailable; retaining last snapshot.")
    try:
        from mlflow.tracking import MlflowClient

        client = MlflowClient(DEFAULT_TRACKING_URI)
        aliases = {}
        for alias in ("champion", "challenger"):
            try:
                aliases[alias] = str(client.get_model_version_by_alias(MODEL_NAME, alias).version)
            except Exception:
                aliases[alias] = None
        versions = sorted(
            client.search_model_versions(f"name='{MODEL_NAME}'"),
            key=lambda v: int(v.version),
            reverse=True,
        )
        history = []
        for version in versions[:15]:
            run = client.get_run(version.run_id)
            mae = run.data.metrics.get("val_mae")
            history.append(
                {
                    "version": str(version.version),
                    "run_id": version.run_id,
                    "timestamp": datetime.fromtimestamp(
                        run.info.start_time / 1000, timezone.utc
                    ).isoformat(),
                    "algorithm": run.data.params.get("model_type", "Unknown"),
                    "val_mae": f"{mae:.4f} RPS" if mae is not None else None,
                    "metrics": run.data.metrics,
                    "tags": dict(version.tags),
                    "stage": "Production (@champion)"
                    if str(version.version) == aliases["champion"]
                    else "Staging (@challenger)"
                    if str(version.version) == aliases["challenger"]
                    else "Archived",
                }
            )
        retraining_history[:] = history
        registry_snapshot.update(aliases=aliases, updated_at=datetime.now(timezone.utc).isoformat())
    except Exception:
        logger.warning("Registry metadata refresh unavailable; retaining last snapshot.")


@app.get("/operations/audit")
def get_operations_audit() -> Dict[str, Any]:
    """Consolidated endpoint providing operational audit history across MLOps lifecycle."""
    aliases = registry_snapshot.get("aliases", {})
    latest_retrain = next(
        (v for v in retraining_history if v["version"] == aliases.get("champion")), {}
    )
    challenger_retrain = next(
        (v for v in retraining_history if v["version"] == aliases.get("challenger")), {}
    )
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "provenance": "live-services",
        "registry_updated_at": registry_snapshot.get("updated_at"),
        "last_ingestion": deepcopy(ingestion_store["last_ingestion"]),
        "ingestion_history": ingestion_store["history"],
        "retraining": {
            "latest": latest_retrain,
            "challenger": challenger_retrain,
            "history": retraining_history,
        },
        "scaling_api": {
            "total_calls_tracked": total_evaluations_count,
            "buffer_window_size": len(scaling_decisions_ring),
            "max_buffer_size": 60,
            "recent_decisions": list(scaling_decisions_ring)[:30],
        },
        "scaling_actions": {
            "total_events_tracked": len(scaling_actions_ring),
            "recent_actions": list(scaling_actions_ring)[:20],
        },
    }


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
WORKLOAD_STATES = {
    "IDLE_SILENT",
    "STEADY_NORMAL",
    "BURST_BUSY",
    "FLASH_ANOMALY",
    "DRIFT_ANOMALY",
    "COOLING_DOWN",
}
workload_coordinator: Dict[str, Any] = {
    "override_state": None,
    "override_id": 0,
    "updated_at": None,
    "daemon_heartbeat": None,
    "daemon_current_state": None,
    "daemon_vus": None,
    "daemon_remaining_s": None,
}
scenario_lock = threading.RLock()
scenario_cancel = threading.Event()
autonomous_drift_coordinator: Dict[str, Any] = {
    "active": False,
    "stage": "IDLE",
    "stage_index": 0,
    "stage_title": "Standby",
    "progress_pct": 0,
    "job_name": None,
    "started_at": None,
    "timeline": [],
    "champion_version": None,
    "previous_version": None,
}


def kubernetes_request(path: str, method: str = "GET", body=None):
    token = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
    if token.exists():
        req = urllib.request.Request(
            "https://kubernetes.default.svc" + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Authorization": f"Bearer {token.read_text().strip()}",
                "Content-Type": "application/json",
            },
            method=method,
        )
        ctx = ssl.create_default_context(
            cafile="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
        )
        with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
            return json.load(response)
    command = [
        "kubectl",
        {"GET": "get", "POST": "create", "DELETE": "delete"}[method],
        "--raw",
        path,
    ]
    if body is not None:
        command += ["-f", "-"]
    result = subprocess.run(
        command,
        input=json.dumps(body) if body is not None else None,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return json.loads(result.stdout)


def _trigger_k8s_retraining_job() -> Optional[str]:
    """Create a job from the deployed training template and return its actual name."""
    try:
        cron = kubernetes_request(
            "/apis/batch/v1/namespaces/mlops/cronjobs/mlops-continuous-training"
        )
        spec = deepcopy(cron["spec"]["jobTemplate"]["spec"])
        spec["activeDeadlineSeconds"] = 900
        name = f"drift-retrain-{uuid4().hex[:12]}"
        created = kubernetes_request(
            "/apis/batch/v1/namespaces/mlops/jobs",
            "POST",
            {
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "name": name,
                    "namespace": "mlops",
                    "labels": {"app.kubernetes.io/managed-by": "mlops-closed-loop-trigger"},
                },
                "spec": spec,
            },
        )
        return created["metadata"]["name"]
    except Exception:
        logger.exception("Training job dispatch failed")
        return None


def _check_k8s_job_status(job_name: str) -> Dict[str, Any]:
    data = kubernetes_request(f"/apis/batch/v1/namespaces/mlops/jobs/{job_name}")
    status = data.get("status", {})
    conditions = {c["type"] for c in status.get("conditions", []) if c.get("status") == "True"}
    return {
        "succeeded": "Complete" in conditions,
        "failed": "Failed" in conditions,
        "active": bool(status.get("active")),
        "completion_time": status.get("completionTime"),
    }


def _job_result(job_name: str) -> Dict[str, Any]:
    pods = kubernetes_request(f"/api/v1/namespaces/mlops/pods?labelSelector=job-name%3D{job_name}")
    for pod in pods["items"]:
        for container in pod["status"].get("containerStatuses", []):
            terminated = container.get("state", {}).get("terminated", {})
            if terminated.get("exitCode") == 0 and terminated.get("message"):
                return json.loads(terminated["message"])
    return {}


def _queue_workload(state: str):
    workload_coordinator.update(
        override_state=state,
        override_id=max(int(time.time() * 1000), workload_coordinator["override_id"] + 1),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


@app.post("/workload/heartbeat")
def record_workload_heartbeat(payload: Dict[str, Any]) -> Dict[str, Any]:
    state = payload.get("current_state")
    try:
        vus, remaining = int(payload["vus"]), int(payload["remaining_seconds"])
        if state not in WORKLOAD_STATES or min(vus, remaining) < 0:
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        raise HTTPException(422, "Invalid daemon heartbeat")
    workload_coordinator.update(
        daemon_heartbeat=time.time(),
        daemon_current_state=state,
        daemon_vus=vus,
        daemon_remaining_s=remaining,
    )
    if workload_coordinator["override_state"] == state:
        workload_coordinator["override_state"] = None
    return {"status": "ok"}


@app.get("/workload/status")
def get_workload_status() -> Dict[str, Any]:
    heartbeat = workload_coordinator["daemon_heartbeat"]
    age = time.time() - heartbeat if heartbeat is not None else None
    return {
        **workload_coordinator,
        "daemon_alive": age is not None and age < 20,
        "last_heartbeat_seconds_ago": round(age, 1) if age is not None else None,
        "pending_age_s": max(0, time.time() - workload_coordinator["override_id"] / 1000)
        if workload_coordinator["override_state"]
        else None,
    }


def _stage(operation_id, index, code, title, **fields):
    with scenario_lock:
        if (
            scenario_cancel.is_set()
            or autonomous_drift_coordinator.get("operation_id") != operation_id
        ):
            raise InterruptedError("Scenario cancelled")
        autonomous_drift_coordinator.update(
            stage=code, stage_title=title, stage_index=index, progress_pct=index * 20, **fields
        )
        for event in autonomous_drift_coordinator["timeline"]:
            if event["status"] == "ACTIVE":
                event["status"] = "COMPLETED"
        autonomous_drift_coordinator["timeline"].insert(
            0,
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stage": code,
                "title": title,
                "status": "ACTIVE" if index < 5 else "COMPLETED",
            },
        )


def _run_autonomous_drift_sequence(operation_id, cancel, inject):
    job_name = None
    try:
        if inject:
            _stage(operation_id, 1, "WORKLOAD", "Waiting for drift profile heartbeat")
            deadline = time.monotonic() + 60
            while workload_coordinator.get("daemon_current_state") != "DRIFT_ANOMALY":
                if cancel.wait(1):
                    raise InterruptedError()
                if time.monotonic() >= deadline:
                    raise RuntimeError("Daemon did not acknowledge drift within 60 seconds")
            _stage(operation_id, 2, "DRIFT", "Evaluating observed telemetry")
            if cancel.wait(15):
                raise InterruptedError()
            drift = evaluate_telemetry_drift()
            _stage(operation_id, 2, "DRIFT", "Observed drift evaluated", drift=drift)
        _stage(operation_id, 3, "TRAINING", "Dispatching Kubernetes training job")
        job_name = _trigger_k8s_retraining_job()
        if not job_name:
            raise RuntimeError("Kubernetes training job could not be created")
        _stage(operation_id, 3, "TRAINING", "Kubernetes training job running", job_name=job_name)
        deadline = time.monotonic() + 960
        while True:
            if cancel.is_set():
                raise InterruptedError()
            status = _check_k8s_job_status(job_name)
            if status["failed"]:
                raise RuntimeError("Kubernetes training job failed; inspect its logs")
            if status["succeeded"]:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("Training job exceeded its completion deadline")
            if cancel.wait(3):
                raise InterruptedError()
        pipeline_result = _job_result(job_name)
        if (
            pipeline_result.get("pipeline_status") != "COMPLETED"
            or pipeline_result.get("inference_reloaded") is not True
        ):
            raise RuntimeError("Job succeeded but training/reload result was not verified")
        promotion = pipeline_result.get("registry_promotion", {})
        _stage(operation_id, 4, "VERIFYING", "Verifying registry champion and serving reload")
        with scenario_lock:
            if cancel.is_set():
                raise InterruptedError()
            if not load_model_from_registry(strict=True):
                raise RuntimeError(
                    "Training completed but registry reload failed; old model retained"
                )
            if model_store.get("version") != f"v{promotion.get('champion_version')}":
                raise RuntimeError("Loaded version does not match the training result champion")
        _sync_live_ingestion_and_mlflow(force=True)
        with scenario_lock:
            champion = next((r for r in retraining_history if "@champion" in r["stage"]), {})
            _stage(
                operation_id,
                5,
                "COMPLETED",
                "Training job completed and champion loaded",
                champion_version=model_store.get("version"),
                metrics={
                    **champion.get("metrics", {}),
                    "candidate_holdout_mae": promotion.get("candidate_mae"),
                    "champion_holdout_mae": promotion.get("champion_mae"),
                },
                quality_gate="PASSED"
                if promotion.get("status") == "PROMOTED"
                else "RETAINED_CHAMPION",
                hot_reload="SUCCESS",
                active=False,
            )
        if inject:
            _queue_workload("STEADY_NORMAL")
    except InterruptedError:
        try:
            if job_name:
                kubernetes_request(
                    f"/apis/batch/v1/namespaces/mlops/jobs/{job_name}",
                    "DELETE",
                    {"propagationPolicy": "Foreground"},
                )
                deadline = time.monotonic() + 90
                while True:
                    try:
                        kubernetes_request(f"/apis/batch/v1/namespaces/mlops/jobs/{job_name}")
                    except urllib.error.HTTPError as exc:
                        if exc.code == 404:
                            break
                        raise
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Job cancellation was not confirmed within 90 seconds")
                    time.sleep(1)
            with scenario_lock:
                if autonomous_drift_coordinator.get("operation_id") == operation_id:
                    autonomous_drift_coordinator.update(
                        active=False,
                        stage="STOPPED",
                        stage_title="Scenario stopped; training job removed",
                    )
        except Exception as exc:
            logger.exception("Scenario job cancellation failed")
            with scenario_lock:
                autonomous_drift_coordinator.update(
                    active=True, stage="STOP_FAILED", stage_title=str(exc), error=str(exc)
                )
    except Exception as exc:
        with scenario_lock:
            if (
                autonomous_drift_coordinator.get("operation_id") == operation_id
                and not cancel.is_set()
            ):
                autonomous_drift_coordinator.update(
                    active=False, stage="FAILED", stage_title=str(exc), error=str(exc)
                )
                autonomous_drift_coordinator["timeline"].insert(
                    0,
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "stage": "FAILED",
                        "title": str(exc),
                        "status": "FAILED",
                    },
                )
        logger.exception("Lifecycle operation failed")


def _start_scenario(inject: bool) -> Dict[str, Any]:
    global scenario_cancel
    with scenario_lock:
        if autonomous_drift_coordinator["active"]:
            raise HTTPException(409, "A training lifecycle is already running")
        if inject and not get_workload_status()["daemon_alive"]:
            raise HTTPException(409, "Traffic daemon is offline")
        scenario_cancel = threading.Event()
        operation_id = uuid4().hex
        autonomous_drift_coordinator.clear()
        autonomous_drift_coordinator.update(
            active=True,
            operation_id=operation_id,
            stage="QUEUED",
            stage_index=0,
            stage_title="Lifecycle accepted",
            progress_pct=0,
            job_name=None,
            timeline=[],
            started_at=time.time(),
            previous_version=model_store.get("version"),
            champion_version=model_store.get("version"),
        )
        if inject:
            _queue_workload("DRIFT_ANOMALY")
        threading.Thread(
            target=_run_autonomous_drift_sequence,
            args=(operation_id, scenario_cancel, inject),
            daemon=True,
        ).start()
        return {
            "status": "ACCEPTED",
            "operation_id": operation_id,
            "champion_version": model_store.get("version"),
            "k8s_job": None,
        }


@app.post("/monitoring/retrain/trigger", status_code=202)
def trigger_event_driven_retraining(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Accept training; completion is reported only after the real job and reload."""
    return _start_scenario(inject=False)


@app.post("/monitoring/autonomous-scenario/start", status_code=202)
def start_autonomous_scenario() -> Dict[str, Any]:
    return _start_scenario(inject=True)


@app.post("/monitoring/autonomous-scenario/stop")
def stop_autonomous_scenario() -> Dict[str, Any]:
    with scenario_lock:
        scenario_cancel.set()
        active = autonomous_drift_coordinator["active"]
        if autonomous_drift_coordinator["stage"] == "STOP_FAILED":
            raise HTTPException(503, "Job cancellation failed; inspect the owned Kubernetes job")
        autonomous_drift_coordinator.update(
            stage="STOPPING" if active else "STOPPED",
            stage_title="Stopping scenario and cancelling its training job"
            if active
            else "Scenario stopped",
        )
        _queue_workload("STEADY_NORMAL")
        return {
            "status": "ok",
            "override_state": "STEADY_NORMAL",
            "stage": autonomous_drift_coordinator["stage"],
        }


@app.post("/workload/trigger")
def trigger_workload_state(payload: Dict[str, Any]) -> Dict[str, Any]:
    state = str(payload.get("state", "")).upper()
    if state not in WORKLOAD_STATES:
        raise HTTPException(422, "Unknown traffic profile")
    if state == "DRIFT_ANOMALY":
        _start_scenario(inject=True)
    elif state in ("STEADY_NORMAL", "IDLE_SILENT") and autonomous_drift_coordinator["active"]:
        stop_autonomous_scenario()
        _queue_workload(state)
    else:
        _queue_workload(state)
    return {
        "status": "ok",
        "override_state": state,
        "override_id": workload_coordinator["override_id"],
    }


@app.get("/monitoring/autonomous-status")
def get_autonomous_status() -> Dict[str, Any]:
    with scenario_lock:
        started = autonomous_drift_coordinator.get("started_at")
        return {
            **deepcopy(autonomous_drift_coordinator),
            "elapsed_seconds": round(time.time() - started, 1) if started else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "next_stage_countdown": None,
        }


@app.get("/cluster/status")
def cluster_status() -> Dict[str, Any]:
    """Return sanitized node, workload and routing inventory from Kubernetes."""
    namespaces = ("mlops", "monitoring", "titipin")
    try:
        nodes = kubernetes_request("/api/v1/nodes")["items"]
        pods = kubernetes_request("/api/v1/pods")["items"]
        services = kubernetes_request("/api/v1/services")["items"]
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scope": list(namespaces),
            "source": "Kubernetes API inventory",
            "nodes": [
                {
                    "name": n["metadata"]["name"],
                    "ready": any(
                        c["type"] == "Ready" and c["status"] == "True"
                        for c in n["status"].get("conditions", [])
                    ),
                    "role": "control-plane"
                    if "node-role.kubernetes.io/control-plane" in n["metadata"].get("labels", {})
                    else "worker",
                    "unschedulable": n.get("spec", {}).get("unschedulable", False),
                    "capacity": {
                        k: n["status"].get("capacity", {}).get(k) for k in ("cpu", "memory", "pods")
                    },
                    "allocatable": {
                        k: n["status"].get("allocatable", {}).get(k)
                        for k in ("cpu", "memory", "pods")
                    },
                    "info": {
                        k: n["status"].get("nodeInfo", {}).get(k)
                        for k in (
                            "architecture",
                            "osImage",
                            "kernelVersion",
                            "kubeletVersion",
                            "containerRuntimeVersion",
                        )
                    },
                    "conditions": [
                        {k: c.get(k) for k in ("type", "status", "reason", "lastTransitionTime")}
                        for c in n["status"].get("conditions", [])
                    ],
                }
                for n in nodes
            ],
            "pods": [
                {
                    "name": p["metadata"]["name"],
                    "namespace": p["metadata"]["namespace"],
                    "node": p["spec"].get("nodeName"),
                    "phase": p["status"].get("phase", "Unknown"),
                    "ready": sum(
                        c.get("ready", False) for c in p["status"].get("containerStatuses", [])
                    ),
                    "containers": len(p["spec"]["containers"]),
                    "created_at": p["metadata"].get("creationTimestamp"),
                    "owner": [
                        {"kind": o.get("kind"), "name": o.get("name")}
                        for o in p["metadata"].get("ownerReferences", [])
                        if o.get("controller")
                    ],
                    "labels": {
                        k: v
                        for k, v in p["metadata"].get("labels", {}).items()
                        if k
                        in (
                            "app",
                            "app.kubernetes.io/name",
                            "app.kubernetes.io/component",
                            "job-name",
                        )
                    },
                    "restarts": sum(
                        c.get("restartCount", 0) for c in p["status"].get("containerStatuses", [])
                    ),
                    "container_details": [
                        {
                            "name": c["name"],
                            "requests": {
                                k: c.get("resources", {}).get("requests", {}).get(k)
                                for k in ("cpu", "memory")
                            },
                            "limits": {
                                k: c.get("resources", {}).get("limits", {}).get(k)
                                for k in ("cpu", "memory")
                            },
                            "ready": next(
                                (
                                    x.get("ready", False)
                                    for x in p["status"].get("containerStatuses", [])
                                    if x["name"] == c["name"]
                                ),
                                False,
                            ),
                            "state": next(
                                (
                                    {
                                        state: {
                                            k: details.get(k)
                                            for k in (
                                                "reason",
                                                "exitCode",
                                                "startedAt",
                                                "finishedAt",
                                            )
                                        }
                                        for state, details in x.get("state", {}).items()
                                    }
                                    for x in p["status"].get("containerStatuses", [])
                                    if x["name"] == c["name"]
                                ),
                                {},
                            ),
                        }
                        for c in p["spec"]["containers"]
                    ],
                }
                for p in pods
                if p["metadata"]["namespace"] in namespaces
            ],
            "services": [
                {
                    "name": service["metadata"]["name"],
                    "namespace": service["metadata"]["namespace"],
                    "type": service["spec"].get("type"),
                    "selector": service["spec"].get("selector", {}),
                    "ports": [
                        {
                            k: port.get(k)
                            for k in ("name", "port", "targetPort", "nodePort", "protocol")
                        }
                        for port in service["spec"].get("ports", [])
                    ],
                }
                for service in services
                if service["metadata"]["namespace"] in namespaces
            ],
        }
    except Exception:
        raise HTTPException(503, "Cluster inventory unavailable")

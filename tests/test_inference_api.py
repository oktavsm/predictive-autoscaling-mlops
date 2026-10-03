"""
Unit and Integration Tests for FastAPI Inference Serving Service.
=================================================================
Verifies endpoints:
  - GET  /health
  - GET  /metrics
  - POST /predict
  - POST /scale-decision
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.inference.service import app, load_model_from_registry, model_store  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def setup_model():
    """Ensure ML model is loaded before running API tests."""
    load_model_from_registry()


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    """Health check endpoint should return 200 and healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert data["service"] == "predictive-autoscaler-inference"
    assert data["target_rps_per_pod"] == 10.0


def test_metrics_endpoint(client):
    """Metrics endpoint should return Prometheus exposition format."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "autoscaler_inference_requests_total" in response.text


def test_predict_normal_traffic(client):
    """Predict endpoint should return valid forecast and replica count for normal traffic."""
    if model_store.get("model") is None:
        pytest.skip("Model not loaded from registry or local artifacts in this environment")

    payload = {
        "request_rate": 15.0,
        "php_cpu_cores": 0.35,
        "p95_latency_seconds": 0.045,
        "php_memory_mb": 120.0,
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["predicted_workload_rps_60s"] >= 0.0
    assert 1 <= data["recommended_replicas"] <= 6
    assert data["target_capacity_rps"] >= 10.0
    assert data["inference_latency_ms"] < 1000.0


def test_predict_spike_traffic(client):
    """Predict endpoint should recommend scaling up on spike traffic."""
    if model_store.get("model") is None:
        pytest.skip("Model not loaded from registry or local artifacts in this environment")

    payload = {
        "request_rate": 35.0,
        "php_cpu_cores": 0.85,
        "p95_latency_seconds": 0.120,
        "php_memory_mb": 160.0,
        "rps_lag1": 25.0,
        "rps_lag2": 15.0,
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["recommended_replicas"] >= 1


def test_scale_decision_k8s_adapter(client):
    """Scale decision endpoint should output valid K8s Custom Resource structure."""
    if model_store.get("model") is None:
        pytest.skip("Model not loaded from registry or local artifacts in this environment")

    payload = {
        "request_rate": 22.0,
        "php_cpu_cores": 0.50,
        "p95_latency_seconds": 0.060,
        "php_memory_mb": 130.0,
    }
    response = client.post("/scale-decision", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["kind"] == "AutoscalingDecision"
    assert "desiredReplicas" in data["spec"]
    assert data["spec"]["policy"]["maxReplicas"] in (4, 6)


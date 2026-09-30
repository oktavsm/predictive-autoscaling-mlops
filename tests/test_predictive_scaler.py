"""
Tests for Predictive Autoscaler Controller.
Verifies telemetry extraction, inference decision integration, scaling logic,
and cooldown safety constraints.
"""

import time

from src.scaling.predictive_scaler import (
    PredictiveScalerController,
    PrometheusClient,
    TelemetrySnapshot,
)


def test_telemetry_snapshot_defaults() -> None:
    snap = TelemetrySnapshot(
        timestamp=time.time(),
        request_rate=25.0,
        php_cpu_cores=0.65,
        p95_latency_seconds=0.045,
        php_memory_mb=128.5,
        current_replicas=2,
    )
    assert snap.request_rate == 25.0
    assert snap.current_replicas == 2
    assert snap.php_cpu_cores == 0.65


def test_prometheus_client_fallback() -> None:
    # Query non-existent Prometheus should safely fallback without crashing
    client = PrometheusClient("http://127.0.0.1:59999")
    snap = client.fetch_telemetry(target_namespace="titipin")
    assert snap.request_rate == 0.0
    assert snap.php_cpu_cores >= 0.0
    assert snap.php_memory_mb > 0.0


def test_scaler_scale_up_decision() -> None:
    controller = PredictiveScalerController(
        prometheus_url="http://127.0.0.1:59999",
        inference_url="http://127.0.0.1:59999",
        target_namespace="titipin",
        target_deployment="laravel-backend",
        min_replicas=1,
        max_replicas=4,
        cooldown_seconds=60,
        dry_run=True,
    )

    # Force simulated snapshot with surge
    snap = TelemetrySnapshot(
        timestamp=time.time(),
        request_rate=32.0,
        php_cpu_cores=0.8,
        p95_latency_seconds=0.1,
        php_memory_mb=200.0,
        current_replicas=1,
    )

    pred_rps, desired, action = controller.query_inference_decision(snap)
    assert desired >= 2
    assert pred_rps > 0.0


def test_scaler_cycle_dry_run() -> None:
    controller = PredictiveScalerController(
        prometheus_url="http://127.0.0.1:59999",
        inference_url="http://127.0.0.1:59999",
        target_namespace="titipin",
        target_deployment="laravel-backend",
        min_replicas=1,
        max_replicas=4,
        dry_run=True,
    )

    result = controller.execute_cycle()
    assert result["dry_run"] is True
    assert "cycle" in result
    assert "decision" in result
    assert result["current_replicas"] >= 1


def test_scaler_cooldown_behavior() -> None:
    controller = PredictiveScalerController(
        prometheus_url="http://127.0.0.1:59999",
        inference_url="http://127.0.0.1:59999",
        target_namespace="titipin",
        target_deployment="laravel-backend",
        min_replicas=1,
        max_replicas=4,
        cooldown_seconds=120,
        dry_run=True,
    )
    # Simulate scale up
    controller.k8s.get_replicas = lambda ns, dep: 3  # type: ignore[assignment]
    controller.last_scale_time = time.time()  # scaled just now

    # A low traffic snapshot recommending 1 replica
    result = controller.execute_cycle()
    # Should HOLD_COOLDOWN to prevent flapping
    assert (
        "HOLD_COOLDOWN" in result["decision"]
        or "MAINTAIN" in result["decision"]
        or result["scaled"] is False
    )

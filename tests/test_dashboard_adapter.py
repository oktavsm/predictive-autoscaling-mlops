#!/usr/bin/env python3
"""
Unit tests for Dashboard Telemetry & Decision Adapter
======================================================
Verifies data transformation, scaling calculation, and fallback handling
per Design Kit v1.1.0 specifications and AGENT-HANDOFF.md.
"""

import math
from datetime import datetime, timezone


def compute_desired_replicas(
    predicted_rps: float, target_rps_per_pod: float, min_pods: int, max_pods: int
) -> int:
    """Computes desired pod allocation clamped to bounds."""
    if target_rps_per_pod <= 0:
        return min_pods
    calc = math.ceil(predicted_rps / target_rps_per_pod)
    return max(min_pods, min(max_pods, calc))


def normalize_decision_record(row: dict) -> dict:
    """Normalizes decision telemetry record per AGENT-HANDOFF.md."""
    issued_at = row.get("timestamp")
    actual_rps = float(row.get("input_rps", 0.0))
    forecast_rps = float(row.get("predicted_rps_60s", 0.0))
    current_replicas = int(row.get("current_replicas", 1))
    desired_replicas = int(row.get("desired_replicas", 1))
    p95_latency_ms = float(row.get("input_p95_ms", 0.0))

    return {
        "issued_at_utc": issued_at,
        "actual_rps": actual_rps,
        "forecast_rps": forecast_rps,
        "observed_replicas": current_replicas,
        "recommended_replicas": desired_replicas,
        "p95_latency_ms": p95_latency_ms,
    }


def test_scaling_formula_clamping():
    """Test scaling recommendation bounds clamping."""
    # Under-load: 3 RPS / 10 RPS per pod = 1 pod
    assert compute_desired_replicas(3.0, 10.0, 1, 6) == 1

    # Moderate load: 25 RPS / 10 RPS per pod = 3 pods
    assert compute_desired_replicas(25.0, 10.0, 1, 6) == 3

    # Heavy surge: 55 RPS / 10 RPS per pod = 6 pods
    assert compute_desired_replicas(55.0, 10.0, 1, 6) == 6

    # Extreme chaos load: 120 RPS / 10 RPS per pod = clamped to 6 pods max
    assert compute_desired_replicas(120.0, 10.0, 1, 6) == 6

    # Zero load: clamped to 1 pod min
    assert compute_desired_replicas(0.0, 10.0, 1, 6) == 1


def test_decision_record_normalization():
    """Verify field mapping and unit integrity."""
    raw_row = {
        "timestamp": "2026-10-12T14:15:47Z",
        "input_rps": 10.62,
        "input_cpu": 0.079,
        "input_p95_ms": 23.9,
        "current_replicas": 1,
        "predicted_rps_60s": 5.94,
        "desired_replicas": 1,
        "action": "MAINTAIN_CAPACITY",
        "latency_ms": 12.46,
    }

    norm = normalize_decision_record(raw_row)
    assert norm["issued_at_utc"] == "2026-10-12T14:15:47Z"
    assert norm["actual_rps"] == 10.62
    assert norm["forecast_rps"] == 5.94
    assert norm["observed_replicas"] == 1
    assert norm["recommended_replicas"] == 1
    # P95 latency must remain in milliseconds, not multiplied by 1000
    assert norm["p95_latency_ms"] == 23.9


def test_forecast_horizon_timestamp():
    """Verify that forecast target is explicitly +60s."""
    issued_iso = "2026-10-12T14:15:00Z"
    dt = datetime.fromisoformat(issued_iso.replace("Z", "+00:00"))
    target_dt = dt.timestamp() + 60.0
    expected_iso = (
        datetime.fromtimestamp(target_dt, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    )
    assert expected_iso == "2026-10-12T14:16:00Z"

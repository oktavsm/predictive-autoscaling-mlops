from datetime import datetime, timedelta, timezone

import pytest
import requests

from src.dashboard.adapter import (
    decision_state,
    normalize_decisions,
    read_resource,
    runtime_policy,
)


@pytest.fixture
def decision():
    return {
        "timestamp": "2026-10-12T14:15:47Z",
        "input_rps": 10.62,
        "input_p95_ms": 23.9,
        "current_replicas": 1,
        "predicted_rps_60s": 5.94,
        "desired_replicas": 2,
    }


def test_real_adapter_units_target_sorting_and_duplicates(decision):
    older = {**decision, "timestamp": "2026-10-12T21:14:47+07:00"}
    rows, rejected = normalize_decisions([decision, older, {**decision, "input_rps": 999}])
    assert rejected == 0
    assert len(rows) == 2
    latest = rows[-1]
    assert latest["actual_rps"] == 10.62
    assert latest["forecast_rps"] == 5.94
    assert latest["p95_latency_ms"] == 23.9
    assert latest["observed_replicas"] == 1
    assert latest["recommended_replicas"] == 2
    assert latest["forecast_target_utc"] - latest["issued_at_utc"] == timedelta(seconds=60)
    assert rows[0]["issued_at_utc"].hour == 14


@pytest.mark.parametrize(
    "field,value",
    [
        ("input_rps", None),
        ("input_rps", -1),
        ("input_rps", float("nan")),
        ("predicted_rps_60s", float("inf")),
        ("current_replicas", 1.5),
        ("desired_replicas", True),
        ("timestamp", "2026-10-12T14:15:47"),
        ("timestamp", "pending"),
    ],
)
def test_invalid_observations_do_not_become_healthy_zeroes(decision, field, value):
    assert normalize_decisions([{**decision, field: value}]) == ([], 1)


def test_missing_fields_and_non_objects(decision):
    assert normalize_decisions([{}, None, "invalid"]) == ([], 3)
    rows, _ = normalize_decisions([{**decision, "synthetic": True}])
    assert rows[0]["synthetic"] is True


def test_states_keep_empty_failed_and_stale_distinct(decision):
    now = datetime(2026, 10, 12, 14, 16, tzinfo=timezone.utc)
    rows, _ = normalize_decisions([decision])
    assert decision_state(rows, 0, None, now, 15) == "ready"
    assert decision_state(rows, 0, None, now + timedelta(minutes=1), 15) == "stale"
    assert decision_state(rows, 0, None, now - timedelta(minutes=2), 15) == "error"
    assert decision_state([], 0, None, now, 15) == "empty"
    assert decision_state([], 1, None, now, 15) == "error"
    assert decision_state([], 0, "unavailable", now, 15) == "error"


def test_runtime_policy_uses_source_and_rejects_invalid_bounds():
    health = {"target_rps_per_pod": 65, "replica_bounds": {"min": 2, "max": 8}}
    assert runtime_policy(health) == {"capacity": 65, "minimum": 2, "maximum": 8}
    assert runtime_policy({**health, "target_rps_per_pod": 0}) is None
    assert runtime_policy({**health, "replica_bounds": {"min": 8, "max": 2}}) is None
    assert runtime_policy({}) is None


def test_read_client_preserves_timeout_shape_and_safe_errors():
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"model_ready": True}

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    result = read_resource("http://internal/", "/health", dict, get)
    assert result["data"]["model_ready"] is True
    assert result["source"] == "/health"
    assert calls == [("http://internal/health", {"timeout": 2.5})]
    assert read_resource("http://internal", "/decisions", list, get)["error"]

    def fail(*args, **kwargs):
        raise requests.Timeout("private URL and credentials")

    result = read_resource("http://internal", "/health", dict, fail)
    assert result["data"] == {}
    assert "private" not in result["error"]

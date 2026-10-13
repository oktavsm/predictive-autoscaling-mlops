"""Auth boundaries, real metric coverage, cache expiry and restart-safe history."""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from src.inference import cluster_metrics as metrics
from src.inference import service as api
from src.inference.operational_store import OperationalStore


@pytest.fixture
def isolated(monkeypatch):
    monkeypatch.setenv("OPERATOR_API_TOKEN", "qa-operator")
    monkeypatch.setenv("SERVICE_API_TOKEN", "qa-service")
    monkeypatch.setattr(api, "operational_store", None)
    monkeypatch.setattr(
        api,
        "autonomous_drift_coordinator",
        {"active": False, "stage": "IDLE", "started_at": None, "finished_at": None, "timeline": []},
    )
    monkeypatch.setattr(api, "workload_coordinator", deepcopy(api.workload_coordinator))
    monkeypatch.setattr(api, "scaling_decisions_ring", api.deque(maxlen=60))
    monkeypatch.setattr(api, "scaling_actions_ring", api.deque(maxlen=40))
    monkeypatch.setattr(api, "scenario_shutdown", api.threading.Event())
    monkeypatch.setattr(api, "scenario_cancel", api.threading.Event())
    return TestClient(api.app)


def test_every_write_denies_anonymous_and_invalid_tokens(isolated):
    for route in api.app.routes:
        if "POST" not in getattr(route, "methods", set()):
            continue
        assert isolated.post(route.path, json={}).status_code == 401, route.path
        assert (
            isolated.post(
                route.path, json={}, headers={"Authorization": "Bearer wrong"}
            ).status_code
            == 401
        )
    assert isolated.get("/health").status_code == 200
    assert isolated.get("/operations/history").status_code == 200
    schema = isolated.get("/openapi.json").json()
    assert "security" not in schema["paths"]["/health"]["get"]
    assert schema["paths"]["/workload/trigger"]["post"]["security"]


def test_token_roles_and_fail_closed_configuration(isolated, monkeypatch):
    operator = {"Authorization": "Bearer qa-operator"}
    service = {"Authorization": "Bearer qa-service"}
    assert isolated.post("/auth/operator", json={}, headers=operator).json()["authenticated"]
    assert isolated.post("/auth/operator", json={}, headers=service).status_code == 403
    body = {"current_state": "STEADY_NORMAL", "vus": 4, "remaining_seconds": 30}
    assert isolated.post("/workload/heartbeat", json=body, headers=operator).status_code == 403
    assert isolated.post("/workload/heartbeat", json=body, headers=service).status_code == 200
    assert (
        isolated.post(
            "/workload/trigger", json={"state": "BURST_BUSY"}, headers=service
        ).status_code
        == 403
    )
    monkeypatch.delenv("SERVICE_API_TOKEN")
    assert isolated.post("/auth/operator", json={}, headers=operator).status_code == 503


def test_sqlite_history_survives_another_process_and_is_bounded(tmp_path):
    path = str(tmp_path / "ops.sqlite")
    db = OperationalStore(path)
    for i in range(7):
        db.append("decisions", {"id": i}, 3)
    db.save_lifecycle({"operation_id": "one", "stage": "STOPPED", "finished_at": 120.0})
    code = 'import json,sys;from src.inference.operational_store import OperationalStore;s=OperationalStore(sys.argv[1]);print(json.dumps([s.recent("decisions",9),s.lifecycle(),s.operations()]))'
    loaded = json.loads(subprocess.check_output([sys.executable, "-c", code, path], text=True))
    assert loaded[0] == [{"id": 6}, {"id": 5}, {"id": 4}]
    assert loaded[1]["finished_at"] == 120.0
    assert len(loaded[2]) == 1


def test_api_restores_rings_and_terminal_state(isolated, tmp_path, monkeypatch):
    path = str(tmp_path / "ops.sqlite")
    db = OperationalStore(path)
    db.append("decisions", {"timestamp": "2026-10-13T01:00:00Z", "input_rps": 12}, 100)
    db.append("actions", {"action": "SCALE_UP"}, 100)
    db.save_lifecycle(
        {
            "active": False,
            "operation_id": "restored",
            "stage": "COMPLETED",
            "started_at": 100.0,
            "finished_at": 125.0,
            "timeline": [],
        }
    )
    monkeypatch.setenv("OPERATIONS_DB_PATH", path)
    api.initialize_operational_store()
    assert api.get_scaling_decisions()[0]["input_rps"] == 12
    assert api.get_scaling_actions()[0]["action"] == "SCALE_UP"
    assert api.get_autonomous_status()["elapsed_seconds"] == 25
    assert api.get_operational_history()["operations"][0]["operation_id"] == "restored"


@pytest.mark.parametrize("stage", ["STOPPED", "FAILED", "COMPLETED"])
def test_terminal_lifecycle_closes_active_stage_and_freezes_elapsed(isolated, monkeypatch, stage):
    api.autonomous_drift_coordinator.update(
        active=True,
        operation_id="op",
        started_at=100.0,
        timeline=[{"status": "ACTIVE", "stage": "TRAINING"}],
    )
    monkeypatch.setattr(api.time, "time", lambda: 130.0)
    api._finish_lifecycle(stage, "Terminal outcome")
    monkeypatch.setattr(api.time, "time", lambda: 999.0)
    assert api.get_autonomous_status()["elapsed_seconds"] == 30
    assert api.autonomous_drift_coordinator["timeline"][1]["status"] != "ACTIVE"
    api.stop_autonomous_scenario()
    assert api.get_autonomous_status()["elapsed_seconds"] == 30


@pytest.mark.parametrize("stage", ["TRAINING", "STOPPING", "STOP_FAILED"])
def test_restart_reconnects_existing_job_without_creating_another(isolated, monkeypatch, stage):
    thread = Mock()
    factory = Mock(return_value=thread)
    monkeypatch.setattr(api.threading, "Thread", factory)
    api.autonomous_drift_coordinator.update(
        active=True, operation_id="saved", job_name="owned-job", inject=True, stage=stage
    )
    api.recover_lifecycle()
    args = factory.call_args.kwargs["args"]
    assert args[0] == "saved" and args[2] is True and args[3] == "owned-job"
    assert args[1].is_set() == (stage in ("STOPPING", "STOP_FAILED"))
    thread.start.assert_called_once()


def test_shutdown_keeps_owned_job_for_restart(isolated, monkeypatch):
    api.autonomous_drift_coordinator.update(active=True, operation_id="saved", job_name="owned-job")
    api.scenario_shutdown.set()
    request = Mock()
    monkeypatch.setattr(api, "kubernetes_request", request)
    api._run_autonomous_drift_sequence("saved", api.scenario_cancel, False, "owned-job")
    request.assert_not_called()
    assert api.autonomous_drift_coordinator["active"] is True


def test_cache_single_flight_expiry_and_timestamp_are_honest(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(metrics.time, "monotonic", lambda: clock[0])
    cache = metrics.SnapshotCache()
    fetch = Mock(side_effect=lambda: {"timestamp": str(clock[0]), "pods": []})
    with ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(lambda _: cache.get(fetch), range(8)))
    assert fetch.call_count == 1 and sum(v["cached"] for v in values) == 7
    clock[0] = 107.0
    result = cache.get(fetch)
    assert result["timestamp"] == "100.0" and result["cache_age_seconds"] == 7
    result["pods"].append("mutated-client-copy")
    assert cache.get(fetch)["pods"] == []
    clock[0] = 109.0
    assert cache.get(fetch)["timestamp"] == "109.0" and fetch.call_count == 2


@pytest.mark.parametrize(
    "value,expected",
    [
        ("250m", 0.25),
        ("2", 2),
        ("64Mi", 67108864),
        ("1e3", 1000),
        ("1Gi", 1073741824),
        (None, None),
        ("invalid", None),
        ("-5", None),
    ],
)
def test_resource_quantity_denominators(value, expected):
    assert metrics.quantity(value) == expected


def test_usage_coverage_limits_zero_and_partial_failure(monkeypatch):
    key = ("mlops", "pod", "api")

    def query(expression):
        return {key: 0.0 if "rate(" in expression else 64 * 1048576}

    monkeypatch.setattr(metrics, "query_usage", query)
    source = {
        "pods": [
            {
                "namespace": "mlops",
                "name": "pod",
                "container_details": [
                    {"name": "api", "limits": {"cpu": "500m", "memory": "128Mi"}}
                ],
            }
        ]
    }
    result = metrics.attach_usage(deepcopy(source))
    usage = result["pods"][0]["usage"]
    assert usage["cpu_cores"] == 0 and usage["cpu_limit_pct"] == 0
    assert usage["memory_limit_pct"] == 50
    source["pods"][0]["container_details"].append({"name": "sidecar", "limits": {}})
    usage = metrics.attach_usage(deepcopy(source))["pods"][0]["usage"]
    assert usage["cpu_cores"] is None and usage["cpu_cores_coverage"] == "1/2"
    assert usage["cpu_limit_pct"] is None
    monkeypatch.setattr(metrics, "query_usage", Mock(side_effect=TimeoutError))
    unavailable = metrics.attach_usage(deepcopy(source))
    assert unavailable["pods"][0]["usage"]["memory_bytes"] is None
    assert unavailable["usage_source"]["status"] == "UNAVAILABLE"

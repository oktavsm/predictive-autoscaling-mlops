"""Operational contracts: real job outcomes, cancellation, registry and telemetry."""

import copy
import json
import threading
import urllib.error
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException

from src.inference import service as api
from src.pipeline.continuous_training import ContinuousTrainingPipeline


@pytest.fixture
def state(monkeypatch):
    for name in ("workload_coordinator", "autonomous_drift_coordinator", "model_store"):
        monkeypatch.setattr(api, name, copy.copy(getattr(api, name)))
    monkeypatch.setattr(api, "scenario_cancel", threading.Event())
    monkeypatch.setattr(api, "scaling_decisions_ring", api.deque(maxlen=60))
    api.autonomous_drift_coordinator.update(
        active=False, operation_id="op", timeline=[], stage="IDLE"
    )
    api.workload_coordinator.update(daemon_heartbeat=None, daemon_current_state=None)
    api.model_store.update(model=object(), version="v7")
    return api


def test_acceptance_is_not_completion_and_duplicate_is_rejected(state, monkeypatch):
    thread = Mock()
    monkeypatch.setattr(api.threading, "Thread", Mock(return_value=thread))
    result = api.trigger_event_driven_retraining({})
    assert result["status"] == "ACCEPTED"
    assert api.get_autonomous_status()["active"] is True
    assert api.get_autonomous_status()["stage"] == "QUEUED"
    assert not api.get_autonomous_status().get("hot_reload")
    with pytest.raises(HTTPException, match="already running"):
        api.trigger_event_driven_retraining({})
    thread.start.assert_called_once()


def test_offline_injector_and_invalid_heartbeat(state):
    with pytest.raises(HTTPException) as exc:
        api.start_autonomous_scenario()
    assert exc.value.status_code == 409
    with pytest.raises(HTTPException) as exc:
        api.record_workload_heartbeat(
            {"current_state": "invented", "vus": 3, "remaining_seconds": 10}
        )
    assert exc.value.status_code == 422
    with pytest.raises(HTTPException):
        api.trigger_workload_state({"state": "invented"})


def test_job_retry_is_not_terminal_failure(state, monkeypatch):
    read = Mock(return_value={"status": {"failed": 1, "active": 1}})
    monkeypatch.setattr(api, "kubernetes_request", read)
    assert api._check_k8s_job_status("job")["failed"] is False
    read.return_value = {"status": {"conditions": [{"type": "Failed", "status": "True"}]}}
    assert api._check_k8s_job_status("job")["failed"] is True


@pytest.mark.parametrize(
    "outcome", ["completed", "failed", "unverified", "reload_failed", "wrong_version"]
)
def test_lifecycle_requires_job_result_and_matching_loaded_version(state, monkeypatch, outcome):
    monkeypatch.setattr(api, "_trigger_k8s_retraining_job", lambda: "job")
    monkeypatch.setattr(
        api,
        "_check_k8s_job_status",
        lambda name: {"succeeded": True, "failed": outcome == "failed"},
    )
    monkeypatch.setattr(
        api,
        "_job_result",
        lambda name: {
            "pipeline_status": "COMPLETED",
            "inference_reloaded": outcome != "unverified",
            "registry_promotion": {"status": "PROMOTED", "champion_version": "8"},
        },
    )

    def reload(strict):
        assert strict
        if outcome != "wrong_version":
            api.model_store["version"] = "v8"
        return outcome != "reload_failed"

    monkeypatch.setattr(api, "load_model_from_registry", reload)
    monkeypatch.setattr(api, "_sync_live_ingestion_and_mlflow", Mock())
    api._run_autonomous_drift_sequence("op", api.scenario_cancel, False)
    result = api.get_autonomous_status()
    assert result["active"] is False
    assert result["stage"] == ("COMPLETED" if outcome == "completed" else "FAILED")
    if outcome == "completed":
        assert result["champion_version"] == "v8"
        assert result["hot_reload"] == "SUCCESS"
    else:
        assert not result.get("hot_reload")


def test_stop_confirms_owned_job_deletion_before_stopped(state, monkeypatch):
    api.autonomous_drift_coordinator["active"] = True
    monkeypatch.setattr(api, "_trigger_k8s_retraining_job", lambda: "owned-job")

    def job_status(name):
        assert api.stop_autonomous_scenario()["stage"] == "STOPPING"
        assert api.autonomous_drift_coordinator["active"]
        return {"succeeded": False, "failed": False}

    monkeypatch.setattr(api, "_check_k8s_job_status", job_status)
    calls = []

    def request(path, method="GET", body=None):
        calls.append((path, method, body))
        if method == "GET":
            raise urllib.error.HTTPError(path, 404, "gone", {}, None)
        return {}

    monkeypatch.setattr(api, "kubernetes_request", request)
    api._run_autonomous_drift_sequence("op", api.scenario_cancel, False)
    assert api.get_autonomous_status()["stage"] == "STOPPED"
    assert api.get_autonomous_status()["active"] is False
    assert calls[0][1:] == ("DELETE", {"propagationPolicy": "Foreground"})
    assert all("owned-job" in c[0] for c in calls)


def test_registry_failure_retains_loaded_model_and_metadata(state, monkeypatch):
    import mlflow.tracking

    monkeypatch.setattr(mlflow.tracking, "MlflowClient", Mock(side_effect=RuntimeError("offline")))
    previous = api.model_store.copy()
    assert api.load_model_from_registry(strict=True) is False
    assert api.model_store == previous


def test_five_feature_psi_uses_real_reference_and_observations(state, monkeypatch, tmp_path):
    ref = pd.DataFrame(
        {
            name: np.arange(1, 21)
            for name in (
                "request_rate",
                "php_cpu_cores",
                "p95_latency_seconds",
                "php_memory_mb",
                "rps_roll_mean_60s",
            )
        }
    )
    path = tmp_path / "reference.csv"
    ref.to_csv(path, index=False)
    monkeypatch.setenv("DRIFT_REFERENCE_PATH", str(path))
    assert api.evaluate_telemetry_drift()["psi_score"] is None
    for i in range(3):
        api.scaling_decisions_ring.append(
            {
                "input_rps": 100 + i,
                "input_cpu": 100 + i,
                "input_p95_ms": 100000 + i * 1000,
                "input_memory_mb": 100 + i,
                "input_rps_roll_mean_60s": 100 + i,
            }
        )
    report = api.evaluate_telemetry_drift()
    assert report["status"] == "DRIFT_DETECTED"
    assert set(report["monitored_features"]) == set(ref.columns)
    assert report["monitored_features"]["p95_latency_seconds"]["live_mean"] == 101
    path.unlink()
    assert api.evaluate_telemetry_drift()["status"] == "REFERENCE_UNAVAILABLE"


def test_cluster_inventory_reads_actual_readiness_without_addresses(state, monkeypatch):
    def request(path):
        if path.endswith("services"):
            return {
                "items": [
                    {
                        "metadata": {"name": "serving", "namespace": "mlops"},
                        "spec": {
                            "type": "NodePort",
                            "clusterIP": "private-service",
                            "selector": {"app": "serving"},
                            "ports": [{"port": 8000, "targetPort": 8000, "nodePort": 30800}],
                        },
                    }
                ]
            }
        if path.endswith("nodes"):
            return {
                "items": [
                    {
                        "metadata": {"name": "worker"},
                        "status": {
                            "conditions": [{"type": "Ready", "status": "False"}],
                            "addresses": [{"address": "private"}],
                            "capacity": {"cpu": "2", "memory": "4000000Ki"},
                            "allocatable": {"cpu": "1900m"},
                        },
                    }
                ]
            }
        return {
            "items": [
                {
                    "metadata": {
                        "name": "serving",
                        "namespace": "mlops",
                        "labels": {"app": "serving", "private": "hidden-label"},
                    },
                    "spec": {
                        "nodeName": "worker",
                        "containers": [
                            {
                                "name": "api",
                                "env": [{"value": "hidden-secret"}],
                                "resources": {"requests": {"cpu": "100m"}},
                            }
                        ],
                    },
                    "status": {
                        "phase": "Running",
                        "podIP": "private-pod",
                        "containerStatuses": [
                            {
                                "name": "api",
                                "ready": False,
                                "restartCount": 3,
                                "state": {
                                    "waiting": {
                                        "reason": "CrashLoopBackOff",
                                        "message": "hidden-log",
                                    }
                                },
                            }
                        ],
                    },
                }
            ]
        }

    monkeypatch.setattr(api, "kubernetes_request", request)
    result = api._read_cluster_inventory()
    assert result["nodes"][0]["ready"] is False
    assert result["pods"][0]["ready"] == 0
    assert result["pods"][0]["restarts"] == 3
    assert result["pods"][0]["container_details"][0]["requests"]["cpu"] == "100m"
    assert (
        result["pods"][0]["container_details"][0]["state"]["waiting"]["reason"]
        == "CrashLoopBackOff"
    )
    assert result["nodes"][0]["allocatable"]["cpu"] == "1900m"
    assert result["services"][0]["ports"][0]["nodePort"] == 30800
    assert result["scope"] == ["mlops", "monitoring", "titipin"]
    assert "private" not in json.dumps(result)
    assert "hidden" not in json.dumps(result)


def test_cluster_inventory_failure_is_explicit(monkeypatch):
    monkeypatch.setattr(
        api, "kubernetes_request", Mock(side_effect=RuntimeError("private server details"))
    )
    with pytest.raises(HTTPException) as exc:
        api._read_cluster_inventory()
    assert exc.value.status_code == 503
    assert exc.value.detail == "Cluster inventory unavailable"


@pytest.mark.parametrize("candidate_error,champion_error,promote", [(1, 2, True), (3, 2, False)])
@pytest.mark.parametrize("delivery_error", [False, True])
def test_shared_holdout_gate_keeps_better_champion(
    monkeypatch, tmp_path, candidate_error, champion_error, promote, delivery_error
):
    import mlflow
    import mlflow.tracking

    from src.models import register_model, train

    monkeypatch.chdir(tmp_path)
    (tmp_path / "models").mkdir()
    (tmp_path / "models/champion_model_metadata.json").write_text(
        json.dumps({"champion_run_id": "run", "champion_model_type": "ridge"})
    )
    validation = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
    targets = pd.Series([0.0, 0.0, 0.0])
    monkeypatch.setattr(
        train, "load_and_prepare_dataset", lambda *args: (None, None, validation, targets, None)
    )
    seen = []

    def load(uri):
        if uri.endswith("/8") and delivery_error:
            raise RuntimeError("Registry artifact delivery failed")
        error = candidate_error if uri.startswith("runs:") else champion_error

        def predict(frame):
            seen.append(frame)
            return np.full(3, error)

        return SimpleNamespace(
            predict=predict, metadata=SimpleNamespace(artifact_path="s3://test/model")
        )

    monkeypatch.setattr(mlflow.pyfunc, "load_model", load)
    client = Mock()
    client.get_model_version_by_alias.return_value = SimpleNamespace(version="7")
    monkeypatch.setattr(mlflow.tracking, "MlflowClient", lambda *args: client)
    monkeypatch.setattr(register_model, "get_or_create_registered_model", Mock())
    monkeypatch.setattr(register_model, "register_model_version", Mock(return_value="8"))
    pipeline = ContinuousTrainingPipeline(
        reference_dataset="reference.csv", tracking_uri="sqlite://"
    )
    if delivery_error:
        with pytest.raises(RuntimeError, match="Registry artifact delivery failed"):
            pipeline.promote_challenger_to_champion()
        client.set_registered_model_alias.assert_not_called()
        return
    result = pipeline.promote_challenger_to_champion()
    assert result["status"] == ("PROMOTED" if promote else "RETAINED_CHAMPION")
    assert result["champion_version"] == ("8" if promote else "7")
    assert seen[0] is seen[1] is validation
    assert (
        register_model.register_model_version.call_args.kwargs["model_source"] == "s3://test/model"
    )
    assert (
        any(c.args[1] == "champion" for c in client.set_registered_model_alias.call_args_list)
        is promote
    )


def test_minio_upload_metadata_and_cas_share_actual_content(monkeypatch, tmp_path):
    from src.data import minio_sync

    path = tmp_path / "telemetry.csv"
    path.write_text("request_rate\n1\n2\n3\n")
    client = Mock()
    client.bucket_exists.return_value = True
    monkeypatch.setattr(minio_sync, "get_minio_client", lambda: (client, "test-bucket"))
    result = minio_sync.push_dataset_to_minio(raw_path=path, processed_path=path)
    assert len(result["pushed_files"]) == 2
    upload = client.fput_object.call_args_list[3]
    assert upload.kwargs["metadata"]["records"] == "3"
    assert upload.kwargs["metadata"]["md5"] == minio_sync.calculate_md5(path)
    assert client.fput_object.call_args_list[-1].args[1] == result["pushed_files"][-1]["dvc_key"]

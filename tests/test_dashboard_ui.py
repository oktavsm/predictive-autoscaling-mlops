"""Exercise dashboard controls with controlled API responses; never contact production."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "src/dashboard/app.py"


def payloads():
    now = datetime.now(timezone.utc)
    decisions = [
        {
            "timestamp": (now - timedelta(seconds=15 * i)).isoformat(),
            "input_rps": 21 - i,
            "input_p95_ms": 23.9,
            "current_replicas": 2,
            "predicted_rps_60s": 35 - i,
            "desired_replicas": 4,
        }
        for i in range(6)
    ]
    return {
        "/health": {
            "status": "healthy",
            "model_ready": True,
            "model_version": "test-v7",
            "model_alias": "champion",
            "model_algorithm": "Fixture model",
            "target_rps_per_pod": 10,
            "replica_bounds": {"min": 1, "max": 8},
        },
        "/scaling/decisions": decisions,
        "/scaling/actions": [
            {
                "timestamp": now.isoformat(),
                "action": "SCALE_UP",
                "from_replicas": 1,
                "to_replicas": 2,
                "status": "applied",
                "synthetic": True,
            }
        ],
        "/operations/audit": {"retraining": {"latest": {"val_mae": "0.4 req/s"}}},
        "/monitoring/drift": {"psi_score": 0.08, "evaluated_cycles": 6},
    }


@pytest.fixture
def render(monkeypatch):
    monkeypatch.syspath_prepend(str(APP.parent))
    calls = []
    data = payloads()

    class Response:
        status_code = 200

        def __init__(self, path):
            self.path = path

        def raise_for_status(self):
            pass

        def json(self):
            value = data.get(self.path, {})
            if isinstance(value, Exception):
                raise value
            return value

    def get(url, **kwargs):
        path = "/" + url.split("/", 3)[-1]
        calls.append(("GET", path))
        return Response(path)

    def forbid_write(*args, **kwargs):
        pytest.fail("Overview attempted an operational write")

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests, "post", forbid_write)
    return AppTest.from_file(str(APP), default_timeout=60), data, calls


def test_overview_renders_and_refresh_is_read_only(render):
    app, data, calls = render
    app.run()
    assert not app.exception
    assert len(app.get("vega_lite_chart")) == 2
    assert [m.value for m in app.metric] == ["Ready", "test-v7", "2", "35.0 req/s"]
    assert set(path for _, path in calls) == set(data)
    assert not any("/workload" in path for _, path in calls)
    app.button[0].click().run()
    assert not app.exception
    assert all(method == "GET" for method, _ in calls)


@pytest.fixture
def operational(render, monkeypatch):
    app, data, calls = render
    data["/workload/status"] = {
        "daemon_alive": True,
        "daemon_current_state": "STEADY_NORMAL",
        "daemon_vus": 6,
        "last_heartbeat_seconds_ago": 2,
    }
    data["/monitoring/autonomous-status"] = {"active": False, "timeline": []}
    data["/monitoring/drift"].update(threshold=0.2)
    writes = {"status": 200, "body": None, "error": None, "calls": []}

    class Response:
        def raise_for_status(self):
            if writes["status"] >= 400:
                raise requests.HTTPError("Private response detail")

        def json(self):
            if isinstance(writes["body"], Exception):
                raise writes["body"]
            return writes["body"]

    def post(url, json, **kwargs):
        path = "/" + url.split("/", 3)[-1]
        writes["calls"].append((path, json))
        if writes["error"]:
            raise writes["error"]
        if writes["body"] is None:
            writes["body"] = {"status": "ok", "override_state": json.get("state")}
        return Response()

    monkeypatch.setattr(requests, "post", post)
    app.run()
    app.toggle[0].set_value(False).run()
    return app, data, writes


def select_page(app, label):
    app.radio[0].set_value(label).run()
    assert not app.exception


def click(app, label):
    button = next(button for button in app.button if button.label == label)
    button.click().run()
    assert not app.exception


def prediction(writes):
    writes["body"] = {
        "status": "SUCCESS",
        "predicted_workload_rps_60s": 35,
        "recommended_replicas": 4,
        "inference_latency_ms": 1.7,
    }


def test_simulator_presets_submission_and_local_policy(operational):
    app, data, writes = operational
    select_page(app, "Scaling Simulator")
    for label, values in (
        ("Quiet (2 RPS)", (2, 0.08, 0.022, 95)),
        ("Normal (12.5 RPS)", (12.5, 0.32, 0.038, 130)),
        ("Surge (35 RPS)", (35, 0.85, 0.085, 165)),
        ("Flash sale (65 RPS)", (65, 1.45, 0.145, 210)),
    ):
        app.slider[0].set_value(21.0).run()
        click(app, label)
        assert [slider.value for slider in app.slider] == list(values)
    prediction(writes)
    click(app, "Compute forecast")
    assert [metric.value for metric in app.metric] == ["35.0 RPS", "4", "4"]
    path, payload = writes["calls"][-1]
    assert path == "/predict" and payload["request_rate"] == 65
    assert payload["php_memory_mb"] == 210 and "rps_lag1" not in payload
    assert 0 <= payload["hour"] <= 23
    app.number_input[0].set_value(20.0).run()
    assert app.metric[-1].value == "2" and app.metric[-2].value == "4"
    assert len(writes["calls"]) == 1
    app.slider[0].set_value(3.0).run()
    assert any("Inputs changed" in warning.value for warning in app.warning)
    assert len(writes["calls"]) == 1


@pytest.mark.parametrize(
    "failure",
    ["400", "503", "timeout", "json", "shape", "missing", "nan", "fractional", "rejected"],
)
def test_prediction_failure_clears_previous_result(operational, failure):
    app, data, writes = operational
    select_page(app, "Scaling Simulator")
    prediction(writes)
    click(app, "Compute forecast")
    assert app.metric
    if failure in ("400", "503"):
        writes["status"] = int(failure)
    elif failure == "timeout":
        writes["error"] = requests.Timeout("Private URL")
    elif failure == "json":
        writes["body"] = ValueError("Invalid JSON")
    elif failure == "shape":
        writes["body"] = [1]
    elif failure == "missing":
        writes["body"] = {"status": "SUCCESS"}
    elif failure == "nan":
        writes["body"]["predicted_workload_rps_60s"] = float("nan")
    elif failure == "fractional":
        writes["body"]["recommended_replicas"] = 1.5
    else:
        writes["body"]["status"] = "ERROR"
    click(app, "Compute forecast")
    assert app.error and not app.metric
    assert "Private" not in " ".join(error.value for error in app.error)


@pytest.mark.parametrize(
    "label,state",
    [
        ("steady normal", "STEADY_NORMAL"),
        ("rush hour", "BURST_BUSY"),
        ("flash sale", "FLASH_ANOMALY"),
        ("cooling down", "COOLING_DOWN"),
        ("quiet night", "IDLE_SILENT"),
    ],
)
def test_workload_profiles_acknowledged_but_not_claimed_applied(operational, label, state):
    app, data, writes = operational
    select_page(app, "Workload Injector")
    click(app, f"Request {label}")
    assert writes["calls"] == [("/workload/trigger", {"state": state})]
    assert any("execution is not yet confirmed" in item.value for item in app.info)
    assert data["/workload/status"]["daemon_current_state"] == "STEADY_NORMAL"
    assert next(button for button in app.button if button.label == "Request drift anomaly").disabled


@pytest.mark.parametrize("failure", ["400", "503", "timeout", "json", "ack"])
def test_workload_failures_are_visible(operational, failure):
    app, data, writes = operational
    select_page(app, "Workload Injector")
    click(app, "Request steady normal")
    assert any("Request accepted" in item.value for item in app.info)
    if failure in ("400", "503"):
        writes["status"] = int(failure)
    elif failure == "timeout":
        writes["error"] = requests.Timeout()
    elif failure == "json":
        writes["body"] = ValueError()
    else:
        writes["body"] = {"status": "ok", "override_state": "WRONG"}
    click(app, "Request rush hour")
    assert app.error
    assert not any("Request accepted" in item.value for item in app.info)


def test_disconnected_generator_disables_every_profile(operational):
    app, data, writes = operational
    data["/workload/status"] = requests.Timeout()
    select_page(app, "Workload Injector")
    assert app.error
    assert all(button.disabled for button in app.button if button.label.startswith("Request "))
    assert not writes["calls"]


def test_accepted_workload_response_and_manual_refresh_controls(operational):
    app, data, writes = operational
    select_page(app, "Workload Injector")
    writes["status"] = 202
    click(app, "Request rush hour")
    assert any("Request accepted" in item.value for item in app.info)
    for page in (
        "Scaling Simulator",
        "Drift & Retraining",
        "FinOps & Carbon",
        "Cluster Architecture",
    ):
        select_page(app, page)
        assert app.toggle[0].disabled and app.select_slider[0].disabled
    assert len(writes["calls"]) == 1


def test_drift_evaluation_and_disabled_retraining(operational):
    app, data, writes = operational
    select_page(app, "Drift & Retraining")
    click(app, "Evaluate telemetry drift (PSI)")
    assert app.metric[0].value == "0.0800"
    assert next(button for button in app.button if button.label == "Trigger retraining").disabled
    data["/monitoring/drift"] = requests.Timeout()
    click(app, "Evaluate telemetry drift (PSI)")
    assert app.error and not app.metric and not writes["calls"]


@pytest.mark.parametrize(
    "value",
    [{"psi_score": float("nan")}, {"psi_score": 0.1, "threshold": 0.2, "evaluated_cycles": 0}, {}],
)
def test_drift_does_not_invent_a_live_verdict(operational, value):
    app, data, writes = operational
    data["/monitoring/drift"] = value
    select_page(app, "Drift & Retraining")
    click(app, "Evaluate telemetry drift (PSI)")
    assert not app.metric


def test_finops_assumptions_control_estimate(operational):
    app, data, writes = operational
    select_page(app, "FinOps & Carbon")
    cost = app.metric[0].value
    app.slider[0].set_value(60).run()
    assert float(app.metric[0].value[1:]) == pytest.approx(float(cost[1:]) * 2, abs=0.01)
    period_cost = float(app.metric[0].value[1:])
    app.number_input[0].set_value(0.035).run()
    assert float(app.metric[0].value[1:]) > period_cost
    dollars = app.metric[0].value
    rupiah = app.dataframe[0].value.iloc[2, 0]
    app.number_input[1].set_value(31600).run()
    assert app.metric[0].value == dollars
    assert app.dataframe[0].value.iloc[2, 0] == pytest.approx(rupiah * 2)
    savings = float(app.metric[1].value[1:])
    app.number_input[2].set_value(10).run()
    assert float(app.metric[1].value[1:]) > savings
    app.number_input[3].set_value(0.0).run()
    assert app.dataframe[0].value.iloc[1, 0] == 0
    predictive = next(
        widget
        for widget in app.number_input
        if widget.label == "Assumed average predictive replicas"
    )
    predictive.set_value(0.0).run()
    assert app.metric[0].value == "$0.00"
    assert not writes["calls"]


@pytest.mark.parametrize(
    "page", ["Telemetry Audit", "Model Registry", "HPA vs Predictive", "Workload Injector"]
)
def test_operational_invalid_sources_render_without_fake_defaults(operational, page):
    app, data, writes = operational
    data.update(
        {
            "/operations/audit": {"retraining": "invalid", "ingestion_history": "invalid"},
            "/telemetry/live-sample": "invalid",
            "/workload/status": [],
            "/monitoring/autonomous-status": {"timeline": 12},
        }
    )
    select_page(app, page)
    assert not writes["calls"]
    assert "0.0880" not in " ".join(metric.value for metric in app.metric)


def test_dashboard_write_routes_and_profile_states_match_service_contract():
    import ast

    repo = APP.parents[2]
    service = ast.parse((repo / "src/inference/service.py").read_text())
    routes = {
        node.args[0].value
        for node in ast.walk(service)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "post"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
    ui = ast.parse(APP.read_text())
    writes = {
        node.args[0].value
        for node in ast.walk(ui)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "post"
    }
    assert writes == {"/predict", "/workload/trigger"} and writes <= routes
    daemon = ast.parse((repo / "workloads/load-generator/traffic_daemon.py").read_text())
    states = next(
        ast.literal_eval(node.value)
        for node in daemon.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "STATES" for target in node.targets)
    )
    profiles = next(
        ast.literal_eval(node.value)
        for node in ast.walk(ui)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "profiles" for target in node.targets)
    )
    assert {state for _, state, _ in profiles} == set(states)


@pytest.mark.parametrize("state", ["empty", "error", "stale", "invalid", "synthetic"])
def test_overview_states_without_fabricated_fallbacks(render, state):
    app, data, calls = render
    if state == "empty":
        data["/scaling/decisions"] = []
    elif state == "error":
        data["/scaling/decisions"] = requests.Timeout("private error")
    elif state == "stale":
        data["/scaling/decisions"][0]["timestamp"] = "2020-01-01T00:00:00Z"
        data["/scaling/decisions"] = data["/scaling/decisions"][:1]
    elif state == "invalid":
        data["/scaling/decisions"] = [{"input_rps": float("nan")}]
        data["/health"] = {"model_ready": False}
    else:
        data["/scaling/decisions"][0]["synthetic"] = True
    app.run()
    assert not app.exception
    if state in ("empty", "error", "invalid"):
        assert app.metric[-1].value == "Unknown"
        assert not app.get("vega_lite_chart")
    elif state in ("stale", "synthetic"):
        assert app.warning
    assert all(method == "GET" for method, _ in calls)


def test_partial_source_failure_keeps_decision_charts(render):
    app, data, calls = render
    data["/health"] = requests.Timeout("private health URL")
    data["/operations/audit"] = {"retraining": "invalid nested object"}
    data["/monitoring/drift"] = {}
    app.run()
    assert not app.exception
    assert app.metric[0].value == "Unavailable"
    assert len(app.get("vega_lite_chart")) == 2


def test_all_existing_workspaces_remain_accessible_without_automatic_writes(render):
    app, data, calls = render
    app.run()
    app.toggle[0].set_value(False).run()
    for page in app.radio[0].options[1:]:
        app.radio[0].set_value(page).run()
        assert not app.exception, page
    assert all(method == "GET" for method, _ in calls)

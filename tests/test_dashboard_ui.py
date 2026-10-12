"""Render Overview with controlled reads; never contact the operational API."""

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

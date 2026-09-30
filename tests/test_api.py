"""API + WebSocket-payload tests using FastAPI's TestClient.

Runs the app in replay mode against the in-memory bus (no Redis, no sensors).
Verifies health, the REST surface, and that the WebSocket emits a payload
containing every field the dashboard relies on.
"""
import os
import time

os.environ.setdefault("SYSTEM_MODE", "replay")
os.environ.setdefault("WINDOW_SECONDS", "1")

import pytest
from fastapi.testclient import TestClient

from backend.main import app

REQUIRED_WS_FIELDS = {
    "timestamp", "network_status", "current_state", "risk", "risk_label",
    "current_stage", "forecast_stage", "future_risk_timeline", "top_features",
    "recent_events", "model_confidence", "sensor_status", "model_status",
    "potential_mitre_mappings",
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        # allow a couple of windows to close so a snapshot is populated
        time.sleep(3)
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["pipeline_running"] is True


def test_config(client):
    r = client.get("/api/config")
    assert r.status_code == 200
    body = r.json()
    assert body["feature_count"] >= 1
    assert len(body["stages"]) >= 2


def test_rest_surface(client):
    for path in ["/api/risk", "/api/forecast", "/api/attack-stage",
                 "/api/explanations", "/api/events", "/api/network/status",
                 "/api/model"]:
        r = client.get(path)
        assert r.status_code == 200, path


def test_websocket_payload_schema(client):
    with client.websocket_connect("/ws/live") as ws:
        data = ws.receive_json()
        missing = REQUIRED_WS_FIELDS - set(data.keys())
        assert not missing, f"missing WS fields: {missing}"
        assert isinstance(data["future_risk_timeline"], list)
        assert isinstance(data["recent_events"], list)

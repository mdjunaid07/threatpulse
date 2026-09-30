"""
backend.services.shared_state — the single in-memory snapshot the API and
WebSocket read from.

The inference pipeline (a background thread) writes the latest forecast
snapshot and recent events here; REST handlers and the WebSocket broadcaster
read from here. All access is guarded by a lock. Nothing here fabricates
data: fields are populated only by the pipeline from real (or clearly-labelled
replay) telemetry and the loaded model.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable, Deque, Dict, List, Optional


class SharedState:
    def __init__(self, max_events: int = 200):
        self._lock = threading.Lock()
        self._snapshot: Dict = _empty_snapshot()
        self._events: Deque[dict] = deque(maxlen=max_events)
        # status providers registered by the app (sensors, bus, replay)
        self._status_providers: Dict[str, Callable[[], dict]] = {}
        self._events_seen = 0
        self._started_at = time.time()

    # ---- snapshot ----
    def set_snapshot(self, snap: dict) -> None:
        with self._lock:
            self._snapshot = snap

    def get_snapshot(self) -> dict:
        with self._lock:
            snap = dict(self._snapshot)
        snap["sensor_status"] = self.sensor_status()
        snap["recent_events"] = self.recent_events(limit=25)
        snap["uptime_seconds"] = round(time.time() - self._started_at, 1)
        return snap

    # ---- events ----
    def add_events(self, events: List[dict]) -> None:
        if not events:
            return
        with self._lock:
            for e in events:
                self._events.append(_event_view(e))
                self._events_seen += 1

    def recent_events(self, limit: int = 25) -> List[dict]:
        with self._lock:
            return list(self._events)[-limit:][::-1]

    @property
    def events_seen(self) -> int:
        with self._lock:
            return self._events_seen

    # ---- status providers ----
    def register_status(self, name: str, provider: Callable[[], dict]) -> None:
        self._status_providers[name] = provider

    def sensor_status(self) -> Dict[str, dict]:
        out = {}
        for name, provider in self._status_providers.items():
            try:
                out[name] = provider()
            except Exception as exc:  # never break a response
                out[name] = {"error": str(exc), "ok": False}
        return out


def _empty_snapshot() -> dict:
    return {
        "timestamp": time.time(),
        "network_status": "INITIALIZING",
        "mode": "unknown",
        "current_state": {},
        "risk": 0.0,
        "risk_label": "N/A",
        "current_stage": {"key": "normal", "label": "Normal"},
        "forecast_stage": {"key": "normal", "label": "Normal"},
        "future_risk_timeline": [],
        "top_features": [],
        "model_confidence": 0.0,
        "model_status": "NOT_TRAINED",
        "dataset_type": "unknown",
        "potential_mitre_mappings": {},
        "active_hosts": 0,
        "active_connections": 0,
        "events_per_sec": 0.0,
    }


def _event_view(e: dict) -> dict:
    """A compact, dashboard-friendly view of one normalized telemetry event."""
    etype = e.get("event_type", "conn")
    if int(e.get("alert", 0)) == 1 or etype == "alert":
        label = e.get("signature") or "IDS Alert"
    else:
        label = _conn_label(e)
    return {
        "ts": e.get("ts", time.time()),
        "source": e.get("source", "unknown"),
        "src_ip": e.get("src_ip", ""),
        "dst_ip": e.get("dst_ip", ""),
        "dst_port": e.get("dst_port", 0),
        "proto": e.get("proto", ""),
        "event": label,
        "severity": e.get("severity", 0),
    }


def _conn_label(e: dict) -> str:
    state = (e.get("conn_state") or "").upper()
    if state in ("S0", "REJ"):
        return "Connection attempt (no reply)"
    if state in ("RSTO", "RSTR", "RSTOS0"):
        return "Reset connection"
    if state == "SF":
        return "Established connection"
    return f"Connection ({state or e.get('proto', 'ip')})"

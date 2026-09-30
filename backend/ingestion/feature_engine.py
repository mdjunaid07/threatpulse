"""
backend.ingestion.feature_engine — consume telemetry from the bus, aggregate
into 10-second windows, and build the network-state history buffer.

This is the runtime bridge between raw events and the model input:

    bus (telemetry:zeek / telemetry:suricata)
      -> WindowAccumulator (10s)
      -> build_feature_vector (feature engine)
      -> NetworkState S(t)
      -> StateHistoryBuffer [S(t-n)..S(t)]

It also publishes each closed state onto the `network:states` stream (for
observability) and forwards the raw events it saw to a callback so the API
can show a live event feed.
"""
from __future__ import annotations

import json
import time
from typing import Callable, List, Optional

import numpy as np

from core.config import Settings
from core.logging_setup import get_logger
from core.schema import FeatureSchema
from features.aggregation import WindowAccumulator
from features.network_features import build_feature_vector
from features.state_builder import NetworkState, StateHistoryBuffer

log = get_logger("feature_engine")


class FeatureEngine:
    def __init__(
        self,
        settings: Settings,
        schema: FeatureSchema,
        bus,
        on_events: Optional[Callable[[List[dict]], None]] = None,
    ):
        self.s = settings
        self.schema = schema
        self.bus = bus
        self.on_events = on_events
        self.accumulator = WindowAccumulator(settings.window_seconds)
        self.history = StateHistoryBuffer(settings.sequence_length, schema.dim)
        self.consumer = bus.consumer()
        self.streams = [
            settings.redis.streams.get("zeek", "telemetry:zeek"),
            settings.redis.streams.get("suricata", "telemetry:suricata"),
        ]
        self.states_stream = settings.redis.streams.get("states", "network:states")
        self._last_window_events = 0
        self._active_hosts: set = set()
        self._active_conns = 0

    def poll_once(self) -> int:
        """Drain new events from all telemetry streams into the accumulator.
        Returns number of events ingested this call."""
        total = 0
        batch: List[dict] = []
        for stream in self.streams:
            events = self.consumer.poll(stream, count=1000)
            if events:
                batch.extend(events)
        if batch:
            self.accumulator.add_many(batch)
            total = len(batch)
            if self.on_events:
                self.on_events(batch)
        return total

    def maybe_close_window(self, now: Optional[float] = None) -> Optional[NetworkState]:
        """If the current window is due, close it into a NetworkState and push
        it onto the history buffer. Returns the new state, or None."""
        now = now if now is not None else time.time()
        if not self.accumulator.due(now):
            return None

        start, end, events = self.accumulator.close(now)
        vec, named = build_feature_vector(events, self.schema, self.s.internal_cidrs)

        # lightweight live counters for the summary cards
        hosts = {e.get("src_ip") for e in events if e.get("src_ip")} | \
                {e.get("dst_ip") for e in events if e.get("dst_ip")}
        conns = sum(1 for e in events if e.get("event_type") == "conn")

        state = NetworkState(
            ts=end,
            window_start=start,
            window_end=end,
            vector=vec,
            named=named,
            event_count=len(events),
            source=self.s.mode,
        )
        self.history.append(state)
        self._last_window_events = len(events)
        self._active_hosts = hosts
        self._active_conns = conns

        # observability: publish the state summary onto its own stream
        try:
            self.bus.publish(self.states_stream, {
                "event_type": "state",
                "ts": end,
                "source": self.s.mode,
                "signature": json.dumps({"features": named, "event_count": len(events)})[:4000],
            })
        except Exception:
            pass

        return state

    def sequence_matrix(self) -> np.ndarray:
        return self.history.sequence_matrix()

    @property
    def summary_counters(self) -> dict:
        return {
            "active_hosts": len(self._active_hosts),
            "active_connections": self._active_conns,
            "events_per_sec": round(self._last_window_events / max(self.s.window_seconds, 1), 2),
            "last_window_events": self._last_window_events,
            "history_len": len(self.history),
            "sequence_ready": self.history.full,
        }

"""
backend.services.pipeline — the continuous inference loop.

Runs in a background thread, independent of any REST request (the spec is
explicit: inference must not be driven by API calls). Each tick it:

    1. drains new telemetry from the bus into the feature engine,
    2. closes a 10-second window when due -> new network state S(t),
    3. runs the World Model on [S(t-n)..S(t)] -> forecast,
    4. writes a fresh snapshot into SharedState (which the WebSocket pushes).

If the model is not trained, it still runs and publishes an honest snapshot
with model_status = NOT_TRAINED (risk/stage left neutral) so the dashboard
reflects reality rather than fabricated numbers.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from core.config import get_settings
from core.logging_setup import get_logger
from core.schema import load_feature_schema, mitre_for_stage
from backend.ingestion.feature_engine import FeatureEngine
from backend.services.shared_state import SharedState
from ml.inference.forecaster import get_forecaster

log = get_logger("pipeline")


class InferencePipeline:
    def __init__(self, bus, shared: SharedState):
        self.s = get_settings()
        self.schema = load_feature_schema()
        self.bus = bus
        self.shared = shared
        self.engine = FeatureEngine(
            self.s, self.schema, bus, on_events=self.shared.add_events
        )
        self.forecaster = get_forecaster()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._poll_interval = 0.25

    def reload_model(self) -> bool:
        ok = self.forecaster.load()
        log.info("model reload requested -> available=%s", self.forecaster.available)
        return ok

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="pipeline", daemon=True)
        self._thread.start()
        log.info("inference pipeline started (window=%ss, seq=%s, mode=%s).",
                 self.s.window_seconds, self.s.sequence_length, self.s.mode)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3.0)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run(self) -> None:
        # Publish an initial snapshot immediately so the dashboard isn't blank.
        self._update_snapshot(new_state=False)
        while not self._stop.is_set():
            try:
                self.engine.poll_once()
                state = self.engine.maybe_close_window()
                if state is not None:
                    self._update_snapshot(new_state=True)
            except Exception as exc:  # pipeline must never die
                log.warning("pipeline tick error: %s", exc)
            self._stop.wait(self._poll_interval)

    def _update_snapshot(self, new_state: bool) -> None:
        counters = self.engine.summary_counters
        seq = self.engine.sequence_matrix()

        result = self.forecaster.forecast(seq)  # honest NOT_TRAINED path inside

        if result.available:
            network_status = _network_status(result.risk, result.current_stage.get("key"))
        else:
            network_status = "MODEL NOT TRAINED"

        snap = {
            "timestamp": time.time(),
            "mode": self.s.mode,
            "network_status": network_status,
            "current_state": (self.engine.history.latest().named
                              if self.engine.history.latest() else {}),
            "risk": result.risk,
            "risk_label": result.risk_label,
            "current_stage": result.current_stage,
            "forecast_stage": result.forecast_stage,
            "stage_distribution": result.stage_distribution,
            "future_risk_timeline": result.future_risk_timeline,
            "top_features": result.top_features,
            "model_confidence": result.model_confidence,
            "model_status": result.model_status,
            "dataset_type": result.dataset_type,
            "potential_mitre_mappings": result.potential_mitre,
            "active_hosts": counters["active_hosts"],
            "active_connections": counters["active_connections"],
            "events_per_sec": counters["events_per_sec"],
            "sequence_ready": counters["sequence_ready"],
            "history_len": counters["history_len"],
            "disclaimer": (
                "Model confidence is the model's own confidence, NOT certainty "
                "that an attack will happen. A forecast is not a guarantee."
            ),
        }
        self.shared.set_snapshot(snap)


def _network_status(risk: float, stage_key: Optional[str]) -> str:
    if stage_key and stage_key != "normal" and risk >= 0.5:
        return "SUSPICIOUS"
    if risk >= 0.5:
        return "ELEVATED"
    if risk >= 0.25:
        return "GUARDED"
    return "NORMAL"

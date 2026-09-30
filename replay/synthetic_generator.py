"""
replay.synthetic_generator — stream synthetic telemetry onto the SAME bus
stream that the live Zeek collector uses.

Critical design rule (from the spec): replay must NOT create a separate
dashboard path. It emits normalized *events* onto `telemetry:zeek` /
`telemetry:suricata` exactly like the real collectors, so the feature engine,
model, API and dashboard are all identical in replay and live mode. The only
difference is the origin of the events, surfaced honestly as SYNTHETIC/REPLAY.

It walks realistic attack episodes:
    NORMAL -> RECONNAISSANCE -> SCANNING -> INCREASED CONNECTIONS ->
    INITIAL-ACCESS-related activity -> (deeper stages) -> back to NORMAL
pausing `window_seconds` of wall-clock between windows so the dashboard
updates at the same cadence as live mode.

Run standalone (writes into Redis if available, else its own in-memory bus —
so for a real demo run it in the SAME process/mode as the backend, or with
Redis running so both processes share the stream):
    python -m replay.synthetic_generator
"""
from __future__ import annotations

import argparse
import threading
import time
from typing import List, Optional

import numpy as np

from core.config import get_settings
from core.logging_setup import get_logger
from ml.preprocessing.synthetic import (
    ESCALATION_PATH,
    generate_episode,
    synthesize_window_events,
)

log = get_logger("replay")


class SyntheticReplay:
    """Emits one window of synthetic events every `window_seconds`."""

    def __init__(self, bus, settings=None, seed: Optional[int] = None):
        self.bus = bus
        self.s = settings or get_settings()
        self.window_seconds = self.s.window_seconds
        self.rng = np.random.default_rng(seed)
        self.zeek_stream = self.s.redis.streams.get("zeek", "telemetry:zeek")
        self.suri_stream = self.s.redis.streams.get("suricata", "telemetry:suricata")
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._current_stage = "normal"
        self._windows_emitted = 0

    @property
    def current_stage(self) -> str:
        return self._current_stage

    @property
    def status(self) -> dict:
        return {
            "name": "replay",
            "running": bool(self._thread and self._thread.is_alive()),
            "current_stage": self._current_stage,
            "windows_emitted": self._windows_emitted,
        }

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="replay", daemon=True)
        self._thread.start()
        log.info("SYNTHETIC replay started (window=%ss). Data is clearly labelled REPLAY.",
                 self.window_seconds)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _emit_window(self, stage_key: str) -> None:
        self._current_stage = stage_key
        now = time.time()
        events = synthesize_window_events(
            stage_key, self.rng, now, self.window_seconds,
            kali_ip=self.s.kali_ip or "10.13.37.5",
            ubuntu_ip=self.s.ubuntu_ip or "10.13.37.10",
        )
        for ev in events:
            # Route alerts to the suricata stream, conns to the zeek stream,
            # mirroring how the two real collectors split telemetry.
            stream = self.suri_stream if ev.get("event_type") == "alert" else self.zeek_stream
            self.bus.publish(stream, ev)
        self._windows_emitted += 1

    def _run(self) -> None:
        while not self._stop.is_set():
            episode = generate_episode(self.rng, max_windows=30)
            log.info("replay episode: %s", " -> ".join(_collapse(episode)))
            for stage_key in episode:
                if self._stop.is_set():
                    break
                self._emit_window(stage_key)
                self._stop.wait(self.window_seconds)
            # brief benign gap between episodes
            for _ in range(2):
                if self._stop.is_set():
                    break
                self._emit_window("normal")
                self._stop.wait(self.window_seconds)


def _collapse(seq: List[str]) -> List[str]:
    out: List[str] = []
    for s in seq:
        if not out or out[-1] != s:
            out.append(s)
    return out


def main():
    ap = argparse.ArgumentParser(description="Synthetic telemetry replay")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--once", action="store_true",
                    help="emit a single scripted escalation then exit")
    args = ap.parse_args()

    from core.bus import get_bus
    bus = get_bus()
    log.info("Replay using bus backend: %s", getattr(bus, "backend", "?"))
    rep = SyntheticReplay(bus, seed=args.seed)

    if args.once:
        for stage in ESCALATION_PATH:
            rep._emit_window(stage)
            log.info("emitted window: %s", stage)
            time.sleep(rep.window_seconds)
        return

    rep.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        rep.stop()
        log.info("replay stopped.")


if __name__ == "__main__":
    main()

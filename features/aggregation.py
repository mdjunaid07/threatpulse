"""
features.aggregation — collect events into fixed 10-second windows.

WindowAccumulator is fed events (from the bus) continuously and, driven by
wall-clock time, closes a window every `window_seconds`, handing back the
list of events that belonged to it. The feature engine then converts that
list into a state vector.

Design decision (wall-clock windows): in a live/replay stream events arrive
continuously; slicing on wall clock gives evenly spaced states S(t) and
avoids depending on perfectly monotonic sensor timestamps.
"""
from __future__ import annotations

import threading
import time
from typing import List, Optional, Tuple


class WindowAccumulator:
    def __init__(self, window_seconds: int):
        self.window_seconds = max(1, int(window_seconds))
        self._lock = threading.Lock()
        self._buffer: List[dict] = []
        self._window_start = time.time()

    def add(self, event: dict) -> None:
        with self._lock:
            self._buffer.append(event)

    def add_many(self, events: List[dict]) -> None:
        if not events:
            return
        with self._lock:
            self._buffer.extend(events)

    def due(self, now: Optional[float] = None) -> bool:
        now = now if now is not None else time.time()
        return (now - self._window_start) >= self.window_seconds

    def close(self, now: Optional[float] = None) -> Tuple[float, float, List[dict]]:
        """Close the current window and start a new one. Returns
        (window_start, window_end, events)."""
        now = now if now is not None else time.time()
        with self._lock:
            events = self._buffer
            start = self._window_start
            self._buffer = []
            self._window_start = now
        return start, now, events

    def pending_count(self) -> int:
        with self._lock:
            return len(self._buffer)

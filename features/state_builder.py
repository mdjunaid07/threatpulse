"""
features.state_builder — the network state S(t) and the rolling history
buffer [S(t-n) .. S(t)] that becomes the model input.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional

import numpy as np


@dataclass
class NetworkState:
    """One 10-second window converted to a feature vector."""
    ts: float                      # window end (epoch seconds)
    window_start: float
    window_end: float
    vector: np.ndarray             # raw (unscaled) feature vector, order = schema
    named: Dict[str, float]        # name -> value (raw)
    event_count: int
    source: str = "unknown"        # which mode produced it: replay/live/hybrid

    def as_dict(self) -> dict:
        return {
            "ts": self.ts,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "event_count": self.event_count,
            "source": self.source,
            "features": self.named,
        }


class StateHistoryBuffer:
    """Fixed-length ring buffer of the most recent states.

    Until it is full it is padded (on read) by repeating the earliest known
    state, so the model always receives a full (sequence_length, dim) input
    even shortly after startup.
    """

    def __init__(self, sequence_length: int, dim: int):
        self.sequence_length = max(1, int(sequence_length))
        self.dim = int(dim)
        self._buf: Deque[NetworkState] = deque(maxlen=self.sequence_length)

    def append(self, state: NetworkState) -> None:
        self._buf.append(state)

    def __len__(self) -> int:
        return len(self._buf)

    @property
    def ready(self) -> bool:
        return len(self._buf) >= 1

    @property
    def full(self) -> bool:
        return len(self._buf) >= self.sequence_length

    def latest(self) -> Optional[NetworkState]:
        return self._buf[-1] if self._buf else None

    def states(self) -> List[NetworkState]:
        return list(self._buf)

    def sequence_matrix(self) -> np.ndarray:
        """Return (sequence_length, dim) of RAW vectors, left-padded by
        repeating the oldest available state. Empty -> zeros."""
        if not self._buf:
            return np.zeros((self.sequence_length, self.dim), dtype=np.float32)
        vecs = [s.vector.astype(np.float32) for s in self._buf]
        if len(vecs) < self.sequence_length:
            pad = [vecs[0]] * (self.sequence_length - len(vecs))
            vecs = pad + vecs
        return np.stack(vecs, axis=0)

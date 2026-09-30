"""
core.bus — event transport with a Redis Streams backend and a transparent
in-memory fallback.

Why: the spec mandates Redis Streams to decouple sensors from the AI
consumer. But the demo must still run when Redis is not installed. So
`get_bus()` tries to connect to Redis; if that fails it returns an
in-process in-memory bus with the SAME interface. No calling code changes.

Interface:
    bus = get_bus()
    bus.publish(stream_name, event_dict)
    consumer = bus.consumer()          # independent cursor per consumer
    events = consumer.poll(stream_name, count=500)   # new events since last poll

Consumers poll (non-blocking). For a 10-second-window system a short poll
interval (100-250 ms) is far more than fast enough, and polling keeps the
cross-thread / async story trivial and robust.
"""
from __future__ import annotations

import itertools
import threading
from typing import Dict, List, Optional

from core.config import get_settings
from core.events import event_from_json, event_to_json, normalize_event

try:
    import redis as _redis  # type: ignore
except Exception:  # pragma: no cover
    _redis = None


# --------------------------------------------------------------------------
# In-memory backend
# --------------------------------------------------------------------------
class _MemoryStore:
    """Process-local, thread-safe append log per stream."""

    def __init__(self, maxlen: int = 20000):
        self._maxlen = maxlen
        self._lock = threading.Lock()
        self._streams: Dict[str, List[tuple]] = {}
        self._seq = itertools.count(1)

    def publish(self, stream: str, event: dict) -> int:
        with self._lock:
            seq = next(self._seq)
            buf = self._streams.setdefault(stream, [])
            buf.append((seq, event))
            if len(buf) > self._maxlen:
                del buf[: len(buf) - self._maxlen]
            return seq

    def tail_seq(self, stream: str) -> int:
        with self._lock:
            buf = self._streams.get(stream)
            return buf[-1][0] if buf else 0

    def read_since(self, stream: str, last_seq: int, count: int):
        with self._lock:
            buf = self._streams.get(stream, [])
            out = [(s, e) for (s, e) in buf if s > last_seq][:count]
            return out


class _MemoryConsumer:
    def __init__(self, store: _MemoryStore):
        self._store = store
        self._cursor: Dict[str, int] = {}

    def poll(self, stream: str, count: int = 500) -> List[dict]:
        last = self._cursor.get(stream)
        if last is None:
            # Fresh consumer starts at the current tail: only new events.
            last = self._store.tail_seq(stream)
            self._cursor[stream] = last
        rows = self._store.read_since(stream, last, count)
        if rows:
            self._cursor[stream] = rows[-1][0]
        return [e for (_s, e) in rows]


class MemoryBus:
    backend = "memory"

    def __init__(self, maxlen: int = 20000):
        self._store = _MemoryStore(maxlen)

    @property
    def available(self) -> bool:
        return True

    def publish(self, stream: str, event: dict) -> None:
        self._store.publish(stream, normalize_event(event))

    def consumer(self) -> _MemoryConsumer:
        return _MemoryConsumer(self._store)

    def ping(self) -> bool:
        return True


# --------------------------------------------------------------------------
# Redis Streams backend
# --------------------------------------------------------------------------
class _RedisConsumer:
    def __init__(self, client, maxlen: int):
        self._c = client
        self._cursor: Dict[str, str] = {}
        self._maxlen = maxlen

    def _init_cursor(self, stream: str) -> str:
        # Start from the current end of the stream so a new consumer only
        # sees new events (mirrors MemoryConsumer semantics).
        try:
            last = self._c.xrevrange(stream, count=1)
            return last[0][0] if last else "0-0"
        except Exception:
            return "0-0"

    def poll(self, stream: str, count: int = 500) -> List[dict]:
        cur = self._cursor.get(stream)
        if cur is None:
            cur = self._init_cursor(stream)
            self._cursor[stream] = cur
        try:
            res = self._c.xread({stream: cur}, count=count, block=None)
        except Exception:
            return []
        if not res:
            return []
        events: List[dict] = []
        for _stream_name, entries in res:
            for entry_id, fields in entries:
                self._cursor[stream] = entry_id
                payload = fields.get("data") or fields.get(b"data")
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8", "replace")
                if payload:
                    events.append(event_from_json(payload))
        return events


class RedisBus:
    backend = "redis"

    def __init__(self, client, maxlen: int):
        self._c = client
        self._maxlen = maxlen

    @property
    def available(self) -> bool:
        return self.ping()

    def publish(self, stream: str, event: dict) -> None:
        try:
            self._c.xadd(
                stream,
                {"data": event_to_json(normalize_event(event))},
                maxlen=self._maxlen,
                approximate=True,
            )
        except Exception:
            # A transient Redis error must not crash a producer.
            pass

    def consumer(self) -> _RedisConsumer:
        return _RedisConsumer(self._c, self._maxlen)

    def ping(self) -> bool:
        try:
            return bool(self._c.ping())
        except Exception:
            return False


# --------------------------------------------------------------------------
# Singleton accessor
# --------------------------------------------------------------------------
_BUS: Optional[object] = None
_BUS_LOCK = threading.Lock()


def _try_redis() -> Optional[RedisBus]:
    if _redis is None:
        return None
    s = get_settings()
    try:
        client = _redis.Redis(
            host=s.redis.host,
            port=s.redis.port,
            db=s.redis.db,
            password=s.redis.password or None,
            socket_connect_timeout=1.0,
            socket_timeout=2.0,
            decode_responses=True,
        )
        if client.ping():
            return RedisBus(client, s.redis.maxlen)
    except Exception:
        return None
    return None


def get_bus(force_memory: bool = False):
    """Return the shared bus. Tries Redis once; falls back to in-memory.
    `force_memory=True` skips Redis (used by unit tests)."""
    global _BUS
    with _BUS_LOCK:
        if _BUS is not None:
            return _BUS
        s = get_settings()
        bus = None
        if not force_memory:
            bus = _try_redis()
        if bus is None:
            bus = MemoryBus(maxlen=s.redis.maxlen)
        _BUS = bus
        return _BUS


def reset_bus():
    """Testing helper: drop the cached bus."""
    global _BUS
    with _BUS_LOCK:
        _BUS = None

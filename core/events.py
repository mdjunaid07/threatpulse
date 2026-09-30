"""
core.events — normalized telemetry event schema.

Zeek conn.log records and Suricata eve.json records are very different on
the wire. Collectors normalize both into a single flat dict shape defined
here, so the feature engine only ever sees one event format regardless of
which sensor (or the replay generator) produced it.

An event is a plain dict (cheap to JSON-serialize onto Redis Streams).
`normalize_event` fills defaults and coerces types so downstream code
never has to guard against missing keys.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict

# Canonical field set. Collectors should populate what they can; the rest
# get safe defaults via normalize_event().
EVENT_FIELDS = (
    "ts",            # float epoch seconds
    "source",        # "zeek" | "suricata" | "replay"
    "event_type",    # "conn" | "alert" | "flow" | "dns" | "http" | ...
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "proto",         # tcp | udp | icmp | ...
    "service",       # http | dns | ssl | "" ...
    "duration",      # seconds
    "orig_bytes",
    "resp_bytes",
    "orig_pkts",
    "resp_pkts",
    "conn_state",    # Zeek conn state: S0, REJ, SF, RSTO, ...
    "history",       # Zeek TCP history string, e.g. "ShADadfF"
    # security / IDS
    "alert",         # 1 if this event is an IDS alert
    "signature",     # alert signature text
    "severity",      # 1 (high) .. 3 (low) per Suricata convention
    "category",      # alert category
)

_DEFAULTS: Dict[str, Any] = {
    "ts": 0.0,
    "source": "unknown",
    "event_type": "conn",
    "src_ip": "",
    "dst_ip": "",
    "src_port": 0,
    "dst_port": 0,
    "proto": "",
    "service": "",
    "duration": 0.0,
    "orig_bytes": 0,
    "resp_bytes": 0,
    "orig_pkts": 0,
    "resp_pkts": 0,
    "conn_state": "",
    "history": "",
    "alert": 0,
    "signature": "",
    "severity": 0,
    "category": "",
}

_FLOAT_FIELDS = {"ts", "duration"}
_INT_FIELDS = {
    "src_port", "dst_port", "orig_bytes", "resp_bytes",
    "orig_pkts", "resp_pkts", "alert", "severity",
}


def _coerce(field: str, value: Any) -> Any:
    try:
        if field in _FLOAT_FIELDS:
            return float(value)
        if field in _INT_FIELDS:
            return int(float(value))
    except (TypeError, ValueError):
        return _DEFAULTS[field]
    return value


def normalize_event(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Return a fully-populated, type-coerced event dict.
    Unknown keys are dropped; missing keys get defaults; ts defaults to now."""
    out: Dict[str, Any] = {}
    for field in EVENT_FIELDS:
        val = raw.get(field, _DEFAULTS[field])
        out[field] = _coerce(field, val)
    if not out["ts"]:
        out["ts"] = time.time()
    return out


def event_to_json(event: Dict[str, Any]) -> str:
    return json.dumps(event, separators=(",", ":"))


def event_from_json(payload: str) -> Dict[str, Any]:
    try:
        return normalize_event(json.loads(payload))
    except (json.JSONDecodeError, TypeError):
        # Malformed events must never crash a consumer; drop to a benign no-op.
        return normalize_event({"event_type": "invalid"})


def is_failed_conn(event: Dict[str, Any]) -> bool:
    """Heuristic: did this connection fail to complete a handshake?
    Used by the feature engine for connection_failure_rate."""
    state = (event.get("conn_state") or "").upper()
    return state in {"S0", "REJ", "RSTO", "RSTOS0", "RSTR", "RSTRH", "SH", "SHR", "OTH"}

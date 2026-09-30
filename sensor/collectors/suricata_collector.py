"""
sensor.collectors.suricata_collector — tail Suricata eve.json and emit
normalized IDS 'alert' (and 'flow') events onto the telemetry bus.

eve.json is one JSON object per line. We care primarily about:
  * event_type == "alert"  -> becomes our alert event (alert=1, severity, sig)
  * event_type == "flow"   -> optional connection-like context

Suricata severity convention: alert.severity 1 = most severe .. 3 = least.
We pass it through unchanged; the feature engine weights it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from core.events import normalize_event
from sensor.collectors.base import TailCollector


class SuricataCollector(TailCollector):
    name = "suricata"

    def parse_line(self, line: str) -> List[dict]:
        line = line.strip()
        if not line or line[0] != "{":
            return []
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return []

        et = obj.get("event_type")
        if et == "alert":
            alert = obj.get("alert", {}) or {}
            ev = {
                "ts": obj.get("timestamp_epoch") or _iso_to_epoch(obj.get("timestamp")),
                "source": "suricata",
                "event_type": "alert",
                "src_ip": obj.get("src_ip", ""),
                "dst_ip": obj.get("dest_ip", ""),
                "src_port": obj.get("src_port", 0) or 0,
                "dst_port": obj.get("dest_port", 0) or 0,
                "proto": (obj.get("proto", "") or "").lower(),
                "alert": 1,
                "signature": alert.get("signature", ""),
                "severity": alert.get("severity", 3),
                "category": alert.get("category", ""),
            }
            return [normalize_event(ev)]

        if et == "flow":
            flow = obj.get("flow", {}) or {}
            ev = {
                "ts": _iso_to_epoch(obj.get("timestamp")),
                "source": "suricata",
                "event_type": "conn",
                "src_ip": obj.get("src_ip", ""),
                "dst_ip": obj.get("dest_ip", ""),
                "src_port": obj.get("src_port", 0) or 0,
                "dst_port": obj.get("dest_port", 0) or 0,
                "proto": (obj.get("proto", "") or "").lower(),
                "orig_bytes": flow.get("bytes_toserver", 0) or 0,
                "resp_bytes": flow.get("bytes_toclient", 0) or 0,
                "orig_pkts": flow.get("pkts_toserver", 0) or 0,
                "resp_pkts": flow.get("pkts_toclient", 0) or 0,
                "conn_state": _flow_state(flow.get("state", "")),
                "history": "",
            }
            return [normalize_event(ev)]

        return []


def _iso_to_epoch(ts) -> float:
    if not ts:
        return 0.0
    try:
        from datetime import datetime
        # Suricata format: 2024-01-01T10:00:00.123456+0000
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _flow_state(state: str) -> str:
    # Coarse map of Suricata flow states to a Zeek-ish conn_state so the
    # feature engine's failure heuristic still works.
    s = (state or "").lower()
    if s in ("new", "closed"):
        return "SF"
    if s in ("established",):
        return "SF"
    return "OTH"


def build_suricata_collector(settings, bus) -> Optional[SuricataCollector]:
    if not settings.suricata_enabled:
        return None
    stream = settings.redis.streams.get("suricata", "telemetry:suricata")
    return SuricataCollector(str(Path(settings.suricata_eve_path)), bus, stream)

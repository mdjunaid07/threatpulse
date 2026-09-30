"""
sensor.collectors.zeek_collector — tail Zeek conn.log and emit normalized
'conn' events onto the telemetry bus.

Zeek conn.log comes in two on-disk formats:
  * TSV (default): '#fields' header line names the columns, then tab-separated
    rows. '#'-prefixed lines are metadata.
  * JSON (if Zeek is configured with json-logs): one JSON object per line.

Both are supported. We map Zeek fields onto our normalized event schema
(core.events). Missing values in Zeek are '-' and are treated as empty.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from core.events import normalize_event
from sensor.collectors.base import TailCollector

# Zeek conn.log field name -> our normalized event field.
ZEEK_CONN_MAP = {
    "ts": "ts",
    "id.orig_h": "src_ip",
    "id.orig_p": "src_port",
    "id.resp_h": "dst_ip",
    "id.resp_p": "dst_port",
    "proto": "proto",
    "service": "service",
    "duration": "duration",
    "orig_bytes": "orig_bytes",
    "resp_bytes": "resp_bytes",
    "orig_pkts": "orig_pkts",
    "resp_pkts": "resp_pkts",
    "conn_state": "conn_state",
    "history": "history",
}


def _clean(v: str):
    return "" if v in ("-", "(empty)", None) else v


class ZeekCollector(TailCollector):
    name = "zeek"

    def __init__(self, path, bus, stream, poll_interval: float = 0.4):
        super().__init__(path, bus, stream, poll_interval)
        self._tsv_fields: Optional[List[str]] = None

    def parse_line(self, line: str) -> List[dict]:
        line = line.rstrip("\n")
        if not line:
            return []
        # JSON mode
        if line[0] == "{":
            return self._parse_json(line)
        # TSV metadata / header
        if line.startswith("#"):
            if line.startswith("#fields"):
                # "#fields\tts\tuid\tid.orig_h\t..."
                parts = line.split("\t")[1:]
                self._tsv_fields = parts
            return []
        return self._parse_tsv(line)

    def _parse_json(self, line: str) -> List[dict]:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return []
        ev = {"source": "zeek", "event_type": "conn"}
        for zk, ek in ZEEK_CONN_MAP.items():
            if zk in obj:
                ev[ek] = _clean(obj[zk])
        return [normalize_event(ev)]

    def _parse_tsv(self, line: str) -> List[dict]:
        if not self._tsv_fields:
            return []
        cols = line.split("\t")
        if len(cols) != len(self._tsv_fields):
            return []
        row = dict(zip(self._tsv_fields, cols))
        ev = {"source": "zeek", "event_type": "conn"}
        for zk, ek in ZEEK_CONN_MAP.items():
            if zk in row:
                ev[ek] = _clean(row[zk])
        return [normalize_event(ev)]


def build_zeek_collector(settings, bus) -> Optional[ZeekCollector]:
    """Construct a Zeek collector from settings. Returns it even if the log
    isn't present yet — the tailer waits for the file to appear."""
    if not settings.zeek_enabled:
        return None
    log_dir = Path(settings.zeek_log_dir)
    conn_path = log_dir / settings.zeek_conn_log
    stream = settings.redis.streams.get("zeek", "telemetry:zeek")
    return ZeekCollector(str(conn_path), bus, stream)

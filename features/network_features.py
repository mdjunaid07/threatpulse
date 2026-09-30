"""
features.network_features — turn a window's worth of normalized telemetry
events into a network-state feature vector.

The ONLY place feature math lives. Output order follows the feature schema
(configs/feature_schema.yaml) exactly, so index i of the returned vector
always corresponds to schema.features[i].

Zeek `history` letters are used for TCP-flag counts. Zeek encodes flags as
letters (S=SYN, A=ACK, F=FIN, R=RST, ...), uppercase for the originator and
lowercase for the responder; we count case-insensitively.
"""
from __future__ import annotations

import ipaddress
import statistics
from typing import Dict, List, Tuple

import numpy as np

from core.events import is_failed_conn
from core.schema import FeatureSchema


def _ip_in_cidrs(ip: str, nets: List[ipaddress._BaseNetwork]) -> bool:
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in n for n in nets)


def _parse_cidrs(cidrs: List[str]) -> List[ipaddress._BaseNetwork]:
    nets = []
    for c in cidrs:
        try:
            nets.append(ipaddress.ip_network(c, strict=False))
        except ValueError:
            continue
    return nets


def _severity_weight(sev: int) -> int:
    # Suricata: 1 = high, 2 = medium, 3 = low. Map to weight 3/2/1.
    return {1: 3, 2: 2, 3: 1}.get(int(sev), 0)


def compute_raw_features(
    events: List[dict],
    window_seconds: int,
    internal_cidrs: List[str],
) -> Dict[str, float]:
    """Compute the named feature dict for one window. Robust to empty input."""
    nets = _parse_cidrs(internal_cidrs)

    conns = [e for e in events if e.get("event_type") == "conn"]
    alerts = [e for e in events if int(e.get("alert", 0)) == 1]

    total_connections = len(conns)
    src_ips = {e["src_ip"] for e in conns if e["src_ip"]}
    dst_ips = {e["dst_ip"] for e in conns if e["dst_ip"]}
    dst_ports = {e["dst_port"] for e in conns if e["dst_port"]}

    # TCP flag counts from Zeek history strings.
    syn = ack = rst = fin = 0
    for e in conns:
        h = (e.get("history") or "").lower()
        syn += h.count("s")
        ack += h.count("a")
        rst += h.count("r")
        fin += h.count("f")

    total_bytes = sum(int(e.get("orig_bytes", 0)) + int(e.get("resp_bytes", 0)) for e in conns)
    total_pkts = sum(int(e.get("orig_pkts", 0)) + int(e.get("resp_pkts", 0)) for e in conns)

    # Inter-arrival times over connection start timestamps.
    ts_sorted = sorted(e["ts"] for e in conns)
    iats = [t2 - t1 for t1, t2 in zip(ts_sorted, ts_sorted[1:])] if len(ts_sorted) > 1 else []
    avg_iat = float(statistics.fmean(iats)) if iats else 0.0
    std_iat = float(statistics.pstdev(iats)) if len(iats) > 1 else 0.0

    failed = sum(1 for e in conns if is_failed_conn(e))
    internal = sum(
        1 for e in conns
        if _ip_in_cidrs(e["src_ip"], nets) and _ip_in_cidrs(e["dst_ip"], nets)
    )

    denom = max(total_connections, 1)
    ws = max(window_seconds, 1)

    feats: Dict[str, float] = {
        "total_connections": float(total_connections),
        "unique_src_ips": float(len(src_ips)),
        "unique_dst_ips": float(len(dst_ips)),
        "unique_dst_ports": float(len(dst_ports)),
        "syn_count": float(syn),
        "ack_count": float(ack),
        "rst_count": float(rst),
        "fin_count": float(fin),
        "syn_ack_ratio": float(syn) / float(max(ack, 1)),
        "rst_ratio": float(rst) / float(denom),
        "avg_packet_size": (float(total_bytes) / float(total_pkts)) if total_pkts else 0.0,
        "bytes_per_sec": float(total_bytes) / float(ws),
        "packets_per_sec": float(total_pkts) / float(ws),
        "avg_iat": avg_iat,
        "std_iat": std_iat,
        "connection_failure_rate": float(failed) / float(denom),
        "dst_diversity": min(1.0, float(len(dst_ports)) / float(denom)),
        "internal_conn_ratio": float(internal) / float(denom),
        "alert_count": float(len(alerts)),
        "alert_severity_sum": float(sum(_severity_weight(e.get("severity", 0)) for e in alerts)),
    }
    return feats


def build_feature_vector(
    events: List[dict],
    schema: FeatureSchema,
    internal_cidrs: List[str],
) -> Tuple[np.ndarray, Dict[str, float]]:
    """Return (ordered float32 vector, named dict). Values are clipped to the
    schema's clip_max before returning; NaN/inf are sanitized to 0."""
    named = compute_raw_features(events, schema.window_seconds, internal_cidrs)
    vec = np.zeros(schema.dim, dtype=np.float32)
    for i, feat in enumerate(schema.features):
        v = float(named.get(feat.name, 0.0))
        if not np.isfinite(v):
            v = 0.0
        if feat.clip_max is not None:
            v = min(v, float(feat.clip_max))
        v = max(v, 0.0)
        vec[i] = v
        named[feat.name] = v
    return vec, named

"""
replay.pcap_replay — OPTIONAL: replay a saved PCAP as telemetry.

This is a convenience path for when you have a capture file and want to feed
it through the SAME pipeline (bus -> feature engine -> model -> dashboard)
without a live sensor. It does NOT re-implement Zeek; it extracts basic
connection-like events from the PCAP using scapy (if installed) and pushes
them onto the zeek telemetry stream, pacing them by their capture timestamps.

If scapy is not installed, it prints a clear message and exits — the primary
fallback for demos remains the synthetic replay, which needs no extra deps.

Usage:
    python -m replay.pcap_replay --file capture.pcap [--speed 1.0]
"""
from __future__ import annotations

import argparse
import time
from typing import Optional

from core.bus import get_bus
from core.config import get_settings
from core.events import normalize_event
from core.logging_setup import get_logger

log = get_logger("pcap_replay")


def _proto_name(pkt) -> str:
    try:
        from scapy.layers.inet import TCP, UDP, ICMP
        if pkt.haslayer(TCP):
            return "tcp"
        if pkt.haslayer(UDP):
            return "udp"
        if pkt.haslayer(ICMP):
            return "icmp"
    except Exception:
        pass
    return ""


def _tcp_history(pkt) -> str:
    try:
        from scapy.layers.inet import TCP
        if not pkt.haslayer(TCP):
            return ""
        flags = pkt[TCP].flags
        hist = ""
        if flags & 0x02:  # SYN
            hist += "S"
        if flags & 0x10:  # ACK
            hist += "a"
        if flags & 0x01:  # FIN
            hist += "f"
        if flags & 0x04:  # RST
            hist += "r"
        return hist
    except Exception:
        return ""


def replay_pcap(path: str, speed: float = 1.0, bus=None, settings=None) -> int:
    try:
        from scapy.all import PcapReader
        from scapy.layers.inet import IP
    except Exception:
        log.error(
            "scapy is not installed. Install it (`pip install scapy`) to use "
            "PCAP replay, or use the synthetic replay instead: "
            "`python -m replay.synthetic_generator`."
        )
        return 0

    settings = settings or get_settings()
    bus = bus or get_bus()
    stream = settings.redis.streams.get("zeek", "telemetry:zeek")

    count = 0
    prev_ts: Optional[float] = None
    log.info("Replaying %s at %.2fx onto %s", path, speed, stream)
    with PcapReader(path) as reader:
        for pkt in reader:
            if not pkt.haslayer(IP):
                continue
            ip = pkt["IP"]
            ts = float(pkt.time)
            if prev_ts is not None and speed > 0:
                delay = max(0.0, (ts - prev_ts) / speed)
                if delay < 5.0:  # avoid huge gaps
                    time.sleep(delay)
            prev_ts = ts

            sport = dport = 0
            try:
                if pkt.haslayer("TCP"):
                    sport, dport = int(pkt["TCP"].sport), int(pkt["TCP"].dport)
                elif pkt.haslayer("UDP"):
                    sport, dport = int(pkt["UDP"].sport), int(pkt["UDP"].dport)
            except Exception:
                pass

            ev = normalize_event({
                "ts": ts,
                "source": "zeek",         # enter via the same stream as Zeek
                "event_type": "conn",
                "src_ip": ip.src,
                "dst_ip": ip.dst,
                "src_port": sport,
                "dst_port": dport,
                "proto": _proto_name(pkt),
                "orig_bytes": int(len(pkt)),
                "resp_bytes": 0,
                "orig_pkts": 1,
                "resp_pkts": 0,
                "conn_state": "OTH",
                "history": _tcp_history(pkt),
            })
            bus.publish(stream, ev)
            count += 1
    log.info("PCAP replay complete: %d packets streamed.", count)
    return count


def main():
    ap = argparse.ArgumentParser(description="Replay a PCAP as telemetry")
    ap.add_argument("--file", required=True)
    ap.add_argument("--speed", type=float, default=1.0)
    args = ap.parse_args()
    replay_pcap(args.file, args.speed)


if __name__ == "__main__":
    main()

"""
ml.preprocessing.synthetic — the shared synthetic-telemetry engine.

This module is the single source of synthetic behaviour, used by BOTH:
  * training-data generation (ml.training.train_lstm), and
  * replay mode (replay.synthetic_generator),
so a model trained on synthetic data sees the exact same feature
distributions that replay produces at runtime. That consistency comes from
one rule: both paths emit normalized *events* here, and both then run those
events through the real feature engine (features.network_features). Nothing
fabricates feature vectors directly.

Honesty note: data produced here is SYNTHETIC. It is for bootstrapping and
demos. Metrics from synthetic data are labelled synthetic everywhere and
must never be presented as real-world validation.

Placeholder IPs use private / documentation ranges (RFC1918, RFC5737) so
nothing here references a real external host.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from core.events import normalize_event
from core.schema import load_stage_space

# Placeholder lab addressing (overridable). Both in 10/8 => "internal".
DEFAULT_KALI_IP = "10.13.37.5"
DEFAULT_UBUNTU_IP = "10.13.37.10"
# Documentation range (RFC5737 TEST-NET-3): stands in for an external peer.
DEFAULT_EXTERNAL_IP = "203.0.113.24"

COMMON_PORTS = [22, 80, 443, 53, 3306, 8080, 25, 21, 3389, 445]


@dataclass
class StageProfile:
    """Parameters controlling how one 10-second window of events looks for a
    given attack stage. Tuned so the feature engine separates the stages."""
    key: str
    conn_lambda: float            # mean number of connection events / window
    port_spread: int              # how many distinct dst ports to sample from
    fail_prob: float              # probability a connection is 'failed'
    syn_heavy: float              # 0..1: fraction of half-open (SYN-only) conns
    alert_lambda: float           # mean IDS alerts / window
    alert_sev: Tuple[int, int]    # (min,max) severity band (1 high..3 low)
    external: bool = False        # talk to an external IP (c2/exfil)
    heavy_bytes: bool = False     # large transfers (exfil)
    beacon: bool = False          # regular inter-arrival (c2)


# Per-stage profiles. Severity/behaviour escalate down the list.
STAGE_PROFILES: Dict[str, StageProfile] = {
    "normal":               StageProfile("normal", 6, 3, 0.03, 0.02, 0.0, (3, 3)),
    "reconnaissance":       StageProfile("reconnaissance", 16, 6, 0.15, 0.15, 0.4, (2, 3)),
    "scanning":             StageProfile("scanning", 120, 400, 0.75, 0.9, 3.0, (2, 3)),
    "initial_access":       StageProfile("initial_access", 40, 4, 0.6, 0.4, 4.0, (1, 2)),
    "execution":            StageProfile("execution", 18, 3, 0.25, 0.2, 3.0, (1, 2)),
    "persistence":          StageProfile("persistence", 12, 3, 0.2, 0.15, 2.0, (1, 3)),
    "privilege_escalation": StageProfile("privilege_escalation", 14, 3, 0.25, 0.2, 3.0, (1, 2)),
    "lateral_movement":     StageProfile("lateral_movement", 30, 8, 0.35, 0.3, 3.5, (1, 2)),
    "command_and_control":  StageProfile("command_and_control", 8, 1, 0.05, 0.05, 2.5, (1, 2),
                                         external=True, beacon=True),
    "exfiltration":         StageProfile("exfiltration", 10, 1, 0.05, 0.05, 2.0, (1, 2),
                                         external=True, heavy_bytes=True),
}


def _pick_ports(rng: np.random.Generator, spread: int) -> np.ndarray:
    spread = max(1, spread)
    if spread <= len(COMMON_PORTS):
        return rng.choice(COMMON_PORTS, size=spread, replace=False)
    # Scan-like: many ports across the low range.
    return rng.integers(1, 1024, size=min(spread, 1000))


def synthesize_window_events(
    stage_key: str,
    rng: np.random.Generator,
    window_start: float,
    window_seconds: int = 10,
    kali_ip: str = DEFAULT_KALI_IP,
    ubuntu_ip: str = DEFAULT_UBUNTU_IP,
    external_ip: str = DEFAULT_EXTERNAL_IP,
) -> List[dict]:
    """Produce a list of normalized events representing one window of the
    given stage. Timestamps are spread across [window_start, window_start+W)."""
    prof = STAGE_PROFILES.get(stage_key, STAGE_PROFILES["normal"])
    n = int(rng.poisson(prof.conn_lambda))
    n = max(0, min(n, 5000))
    events: List[dict] = []

    ports = _pick_ports(rng, prof.port_spread)
    dst_ip = external_ip if prof.external else ubuntu_ip
    src_ip = kali_ip

    if prof.beacon and n > 0:
        # Evenly spaced beacon times.
        times = window_start + np.linspace(0, window_seconds, n, endpoint=False)
    else:
        times = window_start + np.sort(rng.uniform(0, window_seconds, size=n))

    for i in range(n):
        failed = rng.random() < prof.fail_prob
        half_open = rng.random() < prof.syn_heavy
        dport = int(rng.choice(ports))

        if half_open or failed:
            conn_state = rng.choice(["S0", "REJ", "RSTO"])
            history = "S" if half_open else "ShR"
            orig_pkts = int(rng.integers(1, 3))
            resp_pkts = 0 if half_open else int(rng.integers(0, 2))
        else:
            conn_state = "SF"
            history = "ShADadfF"
            orig_pkts = int(rng.integers(3, 20))
            resp_pkts = int(rng.integers(3, 20))

        if prof.heavy_bytes:
            orig_bytes = int(rng.integers(50_000, 500_000))
            resp_bytes = int(rng.integers(500, 5_000))
        else:
            orig_bytes = int(orig_pkts * rng.integers(60, 600))
            resp_bytes = int(resp_pkts * rng.integers(60, 1200))

        events.append(normalize_event({
            "ts": float(times[i]),
            "source": "replay",
            "event_type": "conn",
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "src_port": int(rng.integers(1024, 65535)),
            "dst_port": dport,
            "proto": "tcp",
            "service": {80: "http", 443: "ssl", 53: "dns", 22: "ssh"}.get(dport, ""),
            "duration": float(rng.uniform(0.0, 2.0)),
            "orig_bytes": orig_bytes,
            "resp_bytes": resp_bytes,
            "orig_pkts": orig_pkts,
            "resp_pkts": resp_pkts,
            "conn_state": conn_state,
            "history": history,
        }))

    # IDS alerts for this window.
    n_alerts = int(rng.poisson(prof.alert_lambda))
    for _ in range(min(n_alerts, 50)):
        sev = int(rng.integers(prof.alert_sev[0], prof.alert_sev[1] + 1))
        events.append(normalize_event({
            "ts": float(window_start + rng.uniform(0, window_seconds)),
            "source": "replay",
            "event_type": "alert",
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "dst_port": int(rng.choice(ports)),
            "proto": "tcp",
            "alert": 1,
            "signature": f"SYNTHETIC {stage_key} indicator",
            "severity": sev,
            "category": stage_key,
        }))
    return events


# --------------------------------------------------------------------------
# Episode / progression modelling
# --------------------------------------------------------------------------
# A plausible ordered escalation path. Not every episode reaches the end.
ESCALATION_PATH = [
    "normal",
    "reconnaissance",
    "scanning",
    "initial_access",
    "execution",
    "privilege_escalation",
    "lateral_movement",
    "command_and_control",
    "exfiltration",
]


def generate_episode(rng: np.random.Generator, max_windows: int = 40) -> List[str]:
    """Return a list of stage keys (one per window) for one episode.

    ~40% of episodes are benign (all normal). The rest start normal, then
    escalate along ESCALATION_PATH with random dwell times, stopping at a
    random depth. This gives the model both benign baselines and progressions."""
    if rng.random() < 0.40:
        length = int(rng.integers(8, max_windows))
        return ["normal"] * length

    seq: List[str] = []
    # Warm-up normal windows.
    seq += ["normal"] * int(rng.integers(2, 6))
    depth = int(rng.integers(2, len(ESCALATION_PATH)))  # how far it escalates
    for stage in ESCALATION_PATH[1:depth + 1]:
        dwell = int(rng.integers(2, 6))
        seq += [stage] * dwell
        if len(seq) >= max_windows:
            break
    return seq[:max_windows]


@dataclass
class TrainingArrays:
    X: np.ndarray          # (N, seq_len, dim) raw feature sequences
    y_next: np.ndarray     # (N, dim) next raw state
    y_risk: np.ndarray     # (N,) risk target in [0,1]
    y_stage: np.ndarray    # (N,) stage class id of the LAST window in the seq
    dim: int
    seq_len: int


def _risk_target(stage_key: str, rng: np.random.Generator) -> float:
    space = load_stage_space()
    sev = space.by_key(stage_key).severity
    max_sev = max(s.severity for s in space.stages)
    base = sev / max(max_sev, 1)
    return float(np.clip(base + rng.normal(0, 0.05), 0.0, 1.0))


def build_training_arrays(
    schema,
    internal_cidrs: List[str],
    n_episodes: int = 120,
    sequence_length: int = 10,
    seed: int = 42,
    kali_ip: str = DEFAULT_KALI_IP,
    ubuntu_ip: str = DEFAULT_UBUNTU_IP,
) -> TrainingArrays:
    """Generate synthetic episodes, run each window through the REAL feature
    engine, and assemble supervised sequences with next-state / risk / stage
    targets. Deterministic given `seed`."""
    from features.network_features import build_feature_vector  # local import to avoid cycle

    rng = np.random.default_rng(seed)
    space = load_stage_space()
    key_to_id = {s.key: s.id for s in space.stages}
    dim = schema.dim
    ws = schema.window_seconds

    X_list, ynext_list, yrisk_list, ystage_list = [], [], [], []

    for _ep in range(n_episodes):
        stages = generate_episode(rng)
        vectors: List[np.ndarray] = []
        risks: List[float] = []
        stage_ids: List[int] = []
        wstart = 0.0
        for stage_key in stages:
            events = synthesize_window_events(
                stage_key, rng, wstart, ws, kali_ip, ubuntu_ip
            )
            vec, _named = build_feature_vector(events, schema, internal_cidrs)
            vectors.append(vec)
            risks.append(_risk_target(stage_key, rng))
            stage_ids.append(key_to_id.get(stage_key, 0))
            wstart += ws

        # Slide a window of length L; target is the NEXT window.
        for i in range(len(vectors) - sequence_length):
            seq = np.stack(vectors[i:i + sequence_length], axis=0)
            nxt = vectors[i + sequence_length]
            X_list.append(seq)
            ynext_list.append(nxt)
            yrisk_list.append(risks[i + sequence_length])
            ystage_list.append(stage_ids[i + sequence_length])

    if not X_list:
        # Degenerate guard (should not happen with defaults).
        X_list = [np.zeros((sequence_length, dim), np.float32)]
        ynext_list = [np.zeros(dim, np.float32)]
        yrisk_list = [0.0]
        ystage_list = [0]

    return TrainingArrays(
        X=np.asarray(X_list, dtype=np.float32),
        y_next=np.asarray(ynext_list, dtype=np.float32),
        y_risk=np.asarray(yrisk_list, dtype=np.float32),
        y_stage=np.asarray(ystage_list, dtype=np.int64),
        dim=dim,
        seq_len=sequence_length,
    )

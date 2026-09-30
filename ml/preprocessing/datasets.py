"""
ml.preprocessing.datasets — dataset adapters.

Two sources of training data:

  1. SYNTHETIC (default, always available) — via ml.preprocessing.synthetic.
  2. A generic flow-CSV adapter for public datasets in the style of
     CIC-IDS2018 / CTU-13. Because those datasets are large and are NOT
     shipped with the repo, this adapter is best-effort: point it at a CSV
     with a column map and it will build windowed sequences the same way the
     synthetic path does (real feature engine, same schema).

If no dataset is configured, the trainer falls back to synthetic and labels
the resulting model metadata `training_dataset: synthetic` so the dashboard
can be honest about provenance.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from core.events import normalize_event
from core.schema import load_stage_space

# Default column map for CIC-IDS2018-style flow CSVs. Override as needed.
CICIDS_COLUMN_MAP = {
    "ts": "Timestamp",
    "src_ip": "Src IP",
    "dst_ip": "Dst IP",
    "src_port": "Src Port",
    "dst_port": "Dst Port",
    "proto": "Protocol",
    "orig_bytes": "TotLen Fwd Pkts",
    "resp_bytes": "TotLen Bwd Pkts",
    "orig_pkts": "Tot Fwd Pkts",
    "resp_pkts": "Tot Bwd Pkts",
    "label": "Label",
}

# Map dataset label keywords -> our stage keys (best-effort, case-insensitive).
LABEL_TO_STAGE = [
    ("benign", "normal"),
    ("portscan", "scanning"),
    ("port scan", "scanning"),
    ("scan", "scanning"),
    ("recon", "reconnaissance"),
    ("bruteforce", "initial_access"),
    ("brute force", "initial_access"),
    ("ftp-patator", "initial_access"),
    ("ssh-patator", "initial_access"),
    ("web attack", "initial_access"),
    ("sql injection", "initial_access"),
    ("infiltration", "initial_access"),
    ("bot", "command_and_control"),
    ("ddos", "execution"),
    ("dos", "execution"),
    ("heartbleed", "exfiltration"),
    ("exfil", "exfiltration"),
]


def _label_to_stage_key(label: str) -> str:
    l = str(label).strip().lower()
    for needle, stage in LABEL_TO_STAGE:
        if needle in l:
            return stage
    return "normal"


def csv_available(path: Optional[str]) -> bool:
    return bool(path) and Path(path).exists()


def build_arrays_from_csv(
    csv_path: str,
    schema,
    internal_cidrs: List[str],
    sequence_length: int = 10,
    column_map: Optional[Dict[str, str]] = None,
    max_rows: int = 200_000,
):
    """Build (X, y_next, y_risk, y_stage) from a flow CSV. Returns a
    TrainingArrays-compatible object. Raises on unusable input."""
    import pandas as pd

    from features.network_features import build_feature_vector
    from ml.preprocessing.synthetic import TrainingArrays

    cmap = column_map or CICIDS_COLUMN_MAP
    df = pd.read_csv(csv_path, nrows=max_rows, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]

    def col(key, default=None):
        name = cmap.get(key)
        if name and name in df.columns:
            return df[name]
        return default

    # Order chronologically if a timestamp column exists.
    ts_col = cmap.get("ts")
    if ts_col in df.columns:
        df = df.sort_values(by=ts_col, kind="stable").reset_index(drop=True)

    space = load_stage_space()
    key_to_id = {s.key: s.id for s in space.stages}
    max_sev = max(s.severity for s in space.stages)
    ws = schema.window_seconds

    # Convert each flow row into a normalized 'conn' event.
    events: List[dict] = []
    labels: List[str] = []
    n = len(df)
    for i in range(n):
        row = df.iloc[i]
        label_key = _label_to_stage_key(col("label", default=["normal"] * n)[i] if col("label") is not None else "normal")
        events.append(normalize_event({
            "ts": float(i),  # ordinal time; windows below are index-based
            "source": "dataset",
            "event_type": "conn",
            "src_ip": str(row.get(cmap.get("src_ip", ""), "") or ""),
            "dst_ip": str(row.get(cmap.get("dst_ip", ""), "") or ""),
            "src_port": row.get(cmap.get("src_port", ""), 0) or 0,
            "dst_port": row.get(cmap.get("dst_port", ""), 0) or 0,
            "proto": str(row.get(cmap.get("proto", ""), "") or ""),
            "orig_bytes": row.get(cmap.get("orig_bytes", ""), 0) or 0,
            "resp_bytes": row.get(cmap.get("resp_bytes", ""), 0) or 0,
            "orig_pkts": row.get(cmap.get("orig_pkts", ""), 0) or 0,
            "resp_pkts": row.get(cmap.get("resp_pkts", ""), 0) or 0,
            "conn_state": "SF",
            "history": "ShADadfF",
        }))
        labels.append(label_key)

    # Bucket into fixed-size windows of ~ (rows per 10s). Since dataset time is
    # heterogeneous, we window by a fixed number of flows to form each state.
    flows_per_window = max(20, int(len(events) / max(1, (len(events) // 200) or 1)))
    vectors, risks, stage_ids = [], [], []
    for start in range(0, len(events), flows_per_window):
        chunk = events[start:start + flows_per_window]
        if not chunk:
            continue
        vec, _ = build_feature_vector(chunk, schema, internal_cidrs)
        # window stage = majority non-normal label if present, else normal.
        win_labels = labels[start:start + flows_per_window]
        non_normal = [l for l in win_labels if l != "normal"]
        stage_key = max(set(non_normal), key=non_normal.count) if non_normal else "normal"
        vectors.append(vec)
        stage_ids.append(key_to_id.get(stage_key, 0))
        risks.append(space.by_key(stage_key).severity / max(max_sev, 1))

    X_list, ynext, yrisk, ystage = [], [], [], []
    for i in range(len(vectors) - sequence_length):
        X_list.append(np.stack(vectors[i:i + sequence_length], axis=0))
        ynext.append(vectors[i + sequence_length])
        yrisk.append(risks[i + sequence_length])
        ystage.append(stage_ids[i + sequence_length])

    if not X_list:
        raise ValueError(
            "CSV produced too few windows to form training sequences. "
            "Check the column map and that the file has enough rows."
        )

    return TrainingArrays(
        X=np.asarray(X_list, dtype=np.float32),
        y_next=np.asarray(ynext, dtype=np.float32),
        y_risk=np.asarray(yrisk, dtype=np.float32),
        y_stage=np.asarray(ystage, dtype=np.int64),
        dim=schema.dim,
        seq_len=sequence_length,
    )

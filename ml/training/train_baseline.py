"""
ml.training.train_baseline — a NON-temporal baseline for comparison.

The point of the whole project is the *temporal* World Model. To show
whether temporal information actually helps, we train a simple classifier
that sees only the LAST network state of each sequence (no history) and has
to predict the attack stage. Comparing it with the LSTM (which sees the full
sequence) is the honest way to demonstrate the value of temporal modelling.

Model: LogisticRegression (spec-preferred for simplicity). RandomForest is
available behind --model rf.

Run:
    python -m ml.training.train_baseline
    DATASET_PATH=/path/flows.csv python -m ml.training.train_baseline

Saves: models/baseline.pkl + models/baseline_metadata.json
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import numpy as np

from core.config import get_settings
from core.logging_setup import get_logger
from core.schema import load_feature_schema, load_stage_space
from features.normalization import FeatureScaler

log = get_logger("train_baseline")

try:
    import joblib
except Exception:  # pragma: no cover
    joblib = None


def _build_arrays(schema, settings, seed, episodes):
    """Reuse the exact same array builder as the LSTM trainer so the two
    models are compared on identical data."""
    from ml.training.train_lstm import _build_arrays as build
    return build(schema, settings, seed, episodes)


def _split(n: int, seed: int, val=0.15, test=0.15):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    n_test = int(n * test)
    n_val = int(n * val)
    return idx[n_test + n_val:], idx[n_test:n_test + n_val], idx[:n_test]


def train(model_kind: str = "logreg", seed: int = 42, episodes: int = 160):
    np.random.seed(seed)
    settings = get_settings()
    schema = load_feature_schema()
    space = load_stage_space()

    arrays, dataset_type = _build_arrays(schema, settings, seed, episodes)

    # Baseline input = LAST state of each sequence only (no temporal context).
    X_last = arrays.X[:, -1, :].astype(np.float64)          # (N, dim)
    y_stage = arrays.y_stage.astype(np.int64)

    # Scale with an independent scaler (baseline is standalone).
    scaler = FeatureScaler().fit(X_last)
    Xs = scaler.transform(X_last)

    tr, va, te = _split(len(Xs), seed)

    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier

    if model_kind == "rf":
        clf = RandomForestClassifier(n_estimators=200, random_state=seed, n_jobs=-1)
    else:
        clf = LogisticRegression(max_iter=2000, random_state=seed)

    log.info("Training baseline (%s) on %d samples (last-state only)...",
             model_kind, len(tr))
    clf.fit(Xs[tr], y_stage[tr])

    from sklearn.metrics import accuracy_score, f1_score
    pred = clf.predict(Xs[te])
    metrics = {
        "stage_accuracy": float(accuracy_score(y_stage[te], pred)),
        "stage_f1_macro": float(f1_score(y_stage[te], pred, average="macro", zero_division=0)),
        "test_samples": int(len(te)),
    }
    log.info("BASELINE test  acc=%.3f  f1=%.3f",
             metrics["stage_accuracy"], metrics["stage_f1_macro"])

    if joblib is None:
        raise RuntimeError("joblib required to save the baseline")

    models_dir = settings.abs_path("models")
    models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"clf": clf, "scaler": scaler._scaler, "model_kind": model_kind},
                models_dir / "baseline.pkl")

    metadata = {
        "model_type": f"Baseline ({model_kind}) — non-temporal, last-state only",
        "training_dataset": dataset_type,
        "synthetic_warning": (dataset_type == "synthetic"),
        "feature_count": schema.dim,
        "num_stages": space.num_classes,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "metrics": metrics,
    }
    with open(models_dir / "baseline_metadata.json", "w") as fh:
        json.dump(metadata, fh, indent=2)
    log.info("Saved baseline -> models/baseline.pkl")
    return metadata


def main():
    ap = argparse.ArgumentParser(description="Train the non-temporal baseline")
    ap.add_argument("--model", choices=["logreg", "rf"], default="logreg")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--episodes", type=int, default=160)
    args = ap.parse_args()
    train(model_kind=args.model, seed=args.seed, episodes=args.episodes)


if __name__ == "__main__":
    main()

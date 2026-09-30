"""
ml.training.train_lstm — train the multi-head LSTM World Model.

Pipeline:
    build arrays (synthetic OR dataset CSV)
      -> fit feature scaler (once) and save it
      -> scale inputs + next-state targets
      -> train/val/test split
      -> train (MSE next-state + BCE risk + CE stage)
      -> evaluate on held-out test
      -> save model + scaler + metadata (with dataset provenance & metrics)

Run:
    python -m ml.training.train_lstm                 # synthetic
    DATASET_PATH=/path/flows.csv python -m ml.training.train_lstm

Deterministic given --seed.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from core.config import get_settings
from core.logging_setup import get_logger
from core.schema import load_feature_schema, load_stage_space
from features.normalization import FeatureScaler
from ml.models.lstm_world_model import ModelConfig, build_model

log = get_logger("train_lstm")


def _set_seed(seed: int):
    np.random.seed(seed)
    torch.manual_seed(seed)


def _scale_sequences(scaler: FeatureScaler, X: np.ndarray) -> np.ndarray:
    N, T, F = X.shape
    flat = scaler.transform(X.reshape(N * T, F))
    return flat.reshape(N, T, F).astype(np.float32)


def _split(n: int, seed: int, val=0.15, test=0.15):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    n_test = int(n * test)
    n_val = int(n * val)
    test_idx = idx[:n_test]
    val_idx = idx[n_test:n_test + n_val]
    train_idx = idx[n_test + n_val:]
    return train_idx, val_idx, test_idx


def _build_arrays(schema, settings, seed, episodes):
    import os
    ds_env = os.environ.get("DATASET_PATH", "").strip()
    from ml.preprocessing import datasets as ds
    if ds.csv_available(ds_env):
        log.info("Building training arrays from dataset CSV: %s", ds_env)
        arrays = ds.build_arrays_from_csv(
            ds_env, schema, settings.internal_cidrs,
            sequence_length=settings.sequence_length,
        )
        return arrays, "dataset_csv"
    from ml.preprocessing.synthetic import build_training_arrays
    log.info("No dataset configured -> generating SYNTHETIC training data.")
    arrays = build_training_arrays(
        schema, settings.internal_cidrs,
        n_episodes=episodes,
        sequence_length=settings.sequence_length,
        seed=seed,
        kali_ip=settings.kali_ip or "10.13.37.5",
        ubuntu_ip=settings.ubuntu_ip or "10.13.37.10",
    )
    return arrays, "synthetic"


def train(
    epochs: int = 25,
    batch_size: int = 64,
    lr: float = 1e-3,
    seed: int = 42,
    episodes: int = 160,
):
    _set_seed(seed)
    settings = get_settings()
    schema = load_feature_schema()
    space = load_stage_space()
    device = settings.device

    arrays, dataset_type = _build_arrays(schema, settings, seed, episodes)
    log.info("Dataset: %s sequences, dim=%d, seq_len=%d, classes=%d",
             len(arrays.X), arrays.dim, arrays.seq_len, space.num_classes)

    # --- Fit scaler on the raw feature vectors seen in inputs + targets. ---
    raw_stack = np.concatenate(
        [arrays.X.reshape(-1, arrays.dim), arrays.y_next.reshape(-1, arrays.dim)], axis=0
    )
    scaler = FeatureScaler().fit(raw_stack)

    Xs = _scale_sequences(scaler, arrays.X)
    y_next_s = scaler.transform(arrays.y_next).astype(np.float32)

    tr, va, te = _split(len(Xs), seed)

    def to_t(a):
        return torch.tensor(a, device=device)

    Xt = to_t(Xs)
    yn = to_t(y_next_s)
    yr = to_t(arrays.y_risk.astype(np.float32))
    ystg = to_t(arrays.y_stage.astype(np.int64))

    cfg = ModelConfig(
        feature_dim=arrays.dim,
        num_stages=space.num_classes,
        hidden_size=settings.hidden_size,
        num_layers=settings.num_layers,
        dropout=settings.dropout,
    )
    model = build_model(cfg, device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    mse = nn.MSELoss()
    bce = nn.BCEWithLogitsLoss()
    ce = nn.CrossEntropyLoss()

    def run_batches(indices, train_mode: bool):
        model.train(train_mode)
        total = 0.0
        order = np.random.permutation(indices) if train_mode else indices
        for start in range(0, len(order), batch_size):
            b = order[start:start + batch_size]
            bt = torch.tensor(b, device=device)
            xb = Xt.index_select(0, bt)
            next_pred, risk_logit, stage_logits = model(xb)
            loss = (
                mse(next_pred, yn.index_select(0, bt))
                + bce(risk_logit, yr.index_select(0, bt))
                + ce(stage_logits, ystg.index_select(0, bt))
            )
            if train_mode:
                opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                opt.step()
            total += float(loss.item()) * len(b)
        return total / max(len(order), 1)

    log.info("Training for %d epochs on %s...", epochs, device)
    for ep in range(1, epochs + 1):
        tr_loss = run_batches(tr, True)
        with torch.no_grad():
            va_loss = run_batches(va, False)
        if ep == 1 or ep % 5 == 0 or ep == epochs:
            log.info("epoch %2d/%d  train=%.4f  val=%.4f", ep, epochs, tr_loss, va_loss)

    # --- Test-set metrics ---
    model.eval()
    with torch.no_grad():
        tet = torch.tensor(te, device=device)
        next_pred, risk_logit, stage_logits = model(Xt.index_select(0, tet))
        risk_pred = torch.sigmoid(risk_logit).cpu().numpy()
        stage_pred = stage_logits.argmax(dim=1).cpu().numpy()
        next_pred_np = next_pred.cpu().numpy()

    risk_true = arrays.y_risk[te]
    stage_true = arrays.y_stage[te]
    next_true = y_next_s[te]

    from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error

    metrics = {
        "risk_mae": float(mean_absolute_error(risk_true, risk_pred)),
        "risk_rmse": float(np.sqrt(np.mean((risk_true - risk_pred) ** 2))),
        "stage_accuracy": float(accuracy_score(stage_true, stage_pred)),
        "stage_f1_macro": float(f1_score(stage_true, stage_pred, average="macro", zero_division=0)),
        "next_state_mae": float(np.mean(np.abs(next_true - next_pred_np))),
        "next_state_rmse": float(np.sqrt(np.mean((next_true - next_pred_np) ** 2))),
        "test_samples": int(len(te)),
    }
    log.info("TEST  risk_mae=%.4f  stage_acc=%.3f  stage_f1=%.3f  nextstate_mae=%.4f",
             metrics["risk_mae"], metrics["stage_accuracy"],
             metrics["stage_f1_macro"], metrics["next_state_mae"])

    # --- Save artifacts ---
    models_dir = settings.abs_path("models")
    models_dir.mkdir(parents=True, exist_ok=True)

    torch.save({"state_dict": model.state_dict(), "config": cfg.to_dict()},
               settings.abs_path(settings.model_path))
    scaler.save(settings.abs_path(settings.scaler_path))

    with open(models_dir / "stage_labels.json", "w") as fh:
        json.dump([{"id": s.id, "key": s.key, "label": s.label, "severity": s.severity}
                   for s in space.stages], fh, indent=2)
    with open(models_dir / "feature_schema.json", "w") as fh:
        json.dump({"dim": schema.dim, "names": schema.names, "labels": schema.labels,
                   "window_seconds": schema.window_seconds}, fh, indent=2)

    metadata = {
        "model_version": "1.0.0",
        "model_type": "LSTM World Model (multi-head)",
        "feature_count": schema.dim,
        "sequence_length": settings.sequence_length,
        "forecast_horizon": settings.forecast_horizon,
        "num_stages": space.num_classes,
        "training_dataset": dataset_type,      # synthetic | dataset_csv
        "synthetic_warning": (dataset_type == "synthetic"),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "epochs": epochs,
        "metrics": metrics,
    }
    with open(settings.abs_path(settings.metadata_path), "w") as fh:
        json.dump(metadata, fh, indent=2)

    log.info("Saved model -> %s", settings.model_path)
    log.info("Saved scaler -> %s", settings.scaler_path)
    log.info("Saved metadata -> %s", settings.metadata_path)
    return metadata


def main():
    ap = argparse.ArgumentParser(description="Train the LSTM World Model")
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--episodes", type=int, default=160,
                    help="synthetic episodes (ignored if DATASET_PATH is set)")
    args = ap.parse_args()
    train(epochs=args.epochs, batch_size=args.batch_size, lr=args.lr,
          seed=args.seed, episodes=args.episodes)


if __name__ == "__main__":
    main()

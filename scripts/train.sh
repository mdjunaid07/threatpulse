#!/usr/bin/env bash
# train.sh — train LSTM World Model + baseline, then evaluate (Linux/macOS).
# Uses the synthetic generator unless DATASET_PATH points to a flow CSV.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"

if [ -d .venv ]; then source .venv/bin/activate; fi

echo "==> Training LSTM World Model..."
python -m ml.training.train_lstm "$@"

echo "==> Training non-temporal baseline..."
python -m ml.training.train_baseline

echo "==> Evaluating (LSTM vs baseline)..."
python -m ml.evaluation.evaluate

echo "==> Done. Report: artifacts/evaluation/evaluation_report.md"

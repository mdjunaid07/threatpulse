# train.ps1 — train LSTM World Model + baseline, then evaluate (Windows).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot; Set-Location $Root
if (Test-Path ".venv") { & ".\.venv\Scripts\Activate.ps1" }

Write-Host "==> Training LSTM World Model..."
python -m ml.training.train_lstm @args

Write-Host "==> Training non-temporal baseline..."
python -m ml.training.train_baseline

Write-Host "==> Evaluating (LSTM vs baseline)..."
python -m ml.evaluation.evaluate

Write-Host "==> Done. Report: artifacts/evaluation/evaluation_report.md"

# =====================================================================
# run_all.ps1 — start the full ThreatPulse stack in REPLAY mode (Windows).
#
# Prefers Docker Compose; otherwise runs backend + frontend locally.
# Checks dependencies and prints clear errors.
#
# Usage (PowerShell):
#   .\scripts\run_all.ps1
#   $env:MODE="live"; .\scripts\run_all.ps1
# =====================================================================
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Mode = if ($env:MODE) { $env:MODE } else { "replay" }
Write-Host "==> ThreatPulse starting (mode=$Mode)" -ForegroundColor Cyan

function Have($cmd) { $null -ne (Get-Command $cmd -ErrorAction SilentlyContinue) }

# ---------- Path 1: Docker Compose ----------
if ((Have "docker") -and (docker compose version 2>$null)) {
    Write-Host "==> Docker Compose detected."
    if (-not (Test-Path "models/lstm_world_model.pt")) {
        Write-Host "==> No trained model found. Training synthetic model in a container..."
        docker compose run --rm -e SYSTEM_MODE=$Mode backend python -m ml.training.train_lstm
    }
    Write-Host "==> Bringing up redis + backend + frontend..."
    $env:SYSTEM_MODE = $Mode
    docker compose up --build
    exit 0
}

Write-Host "==> Docker not found; using local processes." -ForegroundColor Yellow

# ---------- Path 2: local ----------
if (-not (Have "python")) { Write-Error "python not found."; exit 1 }
if (-not (Have "node"))   { Write-Error "node not found (needed for the frontend)."; exit 1 }

if (-not (Test-Path ".venv")) {
    Write-Host "==> Creating Python venv..."
    python -m venv .venv
}
& ".\.venv\Scripts\Activate.ps1"
Write-Host "==> Installing Python deps (first run only)..."
pip install -q -r requirements.txt

if (-not (Test-Path ".env")) {
    Write-Host "==> Creating .env from .env.example"
    Copy-Item ".env.example" ".env"
}

if (-not (Test-Path "models/lstm_world_model.pt")) {
    Write-Host "==> Training synthetic model (one-off)..."
    python -m ml.training.train_lstm
}

Write-Host "==> Starting backend on :8000 ..."
$env:SYSTEM_MODE = $Mode
$backend = Start-Process -PassThru python -ArgumentList "-m","backend.main"

Set-Location frontend
if (-not (Test-Path "node_modules")) {
    Write-Host "==> Installing frontend deps (first run only)..."
    npm install
}
Write-Host "==> Starting frontend on :5173 ..."
$frontend = Start-Process -PassThru npm -ArgumentList "run","dev","--","--host","0.0.0.0","--port","5173"
Set-Location $Root

Write-Host ""
Write-Host "==> Dashboard:  http://localhost:5173" -ForegroundColor Green
Write-Host "==> Backend:    http://localhost:8000   (health: /api/health)"
Write-Host "==> WebSocket:  ws://localhost:8000/ws/live"
Write-Host "==> Close this window or press Ctrl+C to stop, then stop the spawned processes."

Wait-Process -Id $backend.Id, $frontend.Id

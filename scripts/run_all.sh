#!/usr/bin/env bash
# =====================================================================
# run_all.sh — start the full ThreatPulse stack in REPLAY mode (Linux/macOS).
#
# Prefers Docker Compose if available. Otherwise falls back to running the
# backend + frontend locally. Checks dependencies and prints clear errors —
# it will NOT silently fail.
#
# Usage:
#   ./scripts/run_all.sh            # replay demo (default)
#   MODE=live ./scripts/run_all.sh  # live sensor mode (needs Zeek/Suricata)
# =====================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="${MODE:-replay}"
echo "==> ThreatPulse starting (mode=$MODE)"

have() { command -v "$1" >/dev/null 2>&1; }

# ---------- Path 1: Docker Compose ----------
if have docker && docker compose version >/dev/null 2>&1; then
  echo "==> Docker Compose detected."
  if [ ! -f models/lstm_world_model.pt ]; then
    echo "==> No trained model found. Training synthetic model in a container..."
    docker compose run --rm -e SYSTEM_MODE="$MODE" backend python -m ml.training.train_lstm
  fi
  echo "==> Bringing up redis + backend + frontend..."
  SYSTEM_MODE="$MODE" docker compose up --build
  exit 0
fi

echo "==> Docker not found; using local processes."

# ---------- Path 2: local ----------
if ! have python3; then echo "ERROR: python3 not found."; exit 1; fi
if ! have node; then echo "ERROR: node not found (needed for the frontend)."; exit 1; fi

# venv
if [ ! -d .venv ]; then
  echo "==> Creating Python venv..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
echo "==> Installing Python deps (first run only)..."
pip install -q -r requirements.txt

# .env
if [ ! -f .env ]; then
  echo "==> Creating .env from .env.example"
  cp .env.example .env
fi

# model
if [ ! -f models/lstm_world_model.pt ]; then
  echo "==> Training synthetic model (one-off)..."
  python -m ml.training.train_lstm
fi

# backend
echo "==> Starting backend on :8000 ..."
SYSTEM_MODE="$MODE" python -m backend.main &
BACKEND_PID=$!

# frontend
cd frontend
if [ ! -d node_modules ]; then
  echo "==> Installing frontend deps (first run only)..."
  npm install
fi
echo "==> Starting frontend on :5173 ..."
npm run dev -- --host 0.0.0.0 --port 5173 &
FRONTEND_PID=$!
cd "$ROOT"

echo ""
echo "==> Dashboard:  http://localhost:5173"
echo "==> Backend:    http://localhost:8000   (health: /api/health)"
echo "==> WebSocket:  ws://localhost:8000/ws/live"
echo "==> Press Ctrl+C to stop."

cleanup() {
  echo ""; echo "==> Stopping..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup INT TERM
wait

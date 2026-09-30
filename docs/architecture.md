# Architecture

ThreatPulse turns live network telemetry into a **temporal forecast** of attack
progression. This document explains each component and why it exists.

## End-to-end pipeline

```
KALI LINUX (controlled attacker)
   │  authorized lab traffic
   ▼
UBUNTU SERVER (victim + sensors + AI backend)
   ├── ZEEK      → conn.log        (network telemetry)
   └── SURICATA  → eve.json        (IDS telemetry)
         │
         ▼
   Collectors (sensor/collectors/*) normalize → one event schema (core/events.py)
         │
         ▼
   REDIS STREAMS  telemetry:zeek / telemetry:suricata   (core/bus.py)
         │            (in-memory fallback if Redis absent — same interface)
         ▼
   FEATURE ENGINE (backend/ingestion/feature_engine.py)
     - WindowAccumulator: fixed 10s windows (features/aggregation.py)
     - build_feature_vector: ~20 features (features/network_features.py)
     - StateHistoryBuffer: [S(t-9)..S(t)]  (features/state_builder.py)
         │
         ▼
   LSTM WORLD MODEL (ml/models/lstm_world_model.py)
     shared encoder → 3 heads:
       next_state (regression) · risk (sigmoid) · stage (softmax)
         │
         ├── K-STEP ROLLOUT (ml/inference/forecaster.py)
         │     predict S(t+1) → feed back → S(t+2)… → future risk timeline
         ├── EXPLAINABILITY (ml/inference/explain.py)  grad×input, SHAP-optional
         └── MITRE MAPPER (core/schema.mitre_for_stage) — potential context
         │
         ▼
   INFERENCE PIPELINE (backend/services/pipeline.py)  ── continuous loop
         │  writes snapshot → SharedState (backend/services/shared_state.py)
         ▼
   FASTAPI (backend/main.py + backend/api/routes.py)
     REST (query) + WebSocket /ws/live (push, backend/websocket/manager.py)
         │
         ▼
   REACT SOC DASHBOARD (frontend/) viewed on the WINDOWS HOST browser
```

## Component rationale (one line each)

- **Collectors tail log files** — decoupled from Zeek/Suricata internals; run
  as an ordinary process; recover if a log is missing or rotated.
- **One normalized event schema** — the feature engine never cares whether an
  event came from Zeek, Suricata, replay, or a PCAP.
- **Redis Streams** — decouples telemetry producers from the AI consumer while
  staying lightweight; an in-memory bus with the same API keeps demos running
  without Redis.
- **10-second windows** — convert high-volume events into evenly spaced,
  model-friendly network states.
- **Feature schema as single source of truth** — `configs/feature_schema.yaml`
  defines the vector order and length; nothing hard-codes feature counts.
- **LSTM World Model** — learns temporal dependencies between states with modest
  CPU/RAM; the next-state head enables forward simulation.
- **K-step autoregressive rollout** — produces the *forecast* (the project's
  core), not just a current-window label.
- **Gradient attribution** — fast, exact-for-this-model explanations in the live
  loop; SHAP optional.
- **Continuous inference loop in a background thread** — inference is driven by
  telemetry/time, **not** by REST requests (REST only queries the latest state).
- **WebSocket broadcaster** — live updates without polling; one bad client
  cannot stop others.
- **SharedState** — a single locked snapshot both REST and WebSocket read, so
  they never disagree.

## Modes

| Mode | Sources started | Use |
|---|---|---|
| `replay` | synthetic generator → same streams | demo/dev without lab hardware |
| `live` | Zeek + Suricata collectors | real Kali→Ubuntu lab |
| `hybrid` | both | live sensors plus background replay |

Set with `SYSTEM_MODE` in `.env`.

## Honesty guarantees

- No hard-coded risk/stage values anywhere; all forecast numbers come from the
  model.
- Untrained model → `MODEL NOT TRAINED` surfaced to the UI.
- Synthetic/replay provenance is stamped in model metadata and shown as a badge.
- Sensor/bus/model health is reported truthfully (offline/disconnected states).

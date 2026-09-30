# ThreatPulse — AI-Based Network Attack Forecasting

**Team NeuroVex · Smart India Hackathon 2026**

> An AI-powered real-time SOC platform that learns the temporal evolution of
> network traffic using an LSTM **World Model** and **forecasts possible future
> attack progression** before it fully develops — with explainable risk,
> attack-stage prediction, MITRE ATT&CK context, and a live dashboard.

---

## 1. What this is

ThreatPulse continuously monitors authorized lab network traffic, converts it
into **10-second time-windowed network states**, feeds the sequence of states
into a PyTorch **LSTM World Model**, and forecasts how the network *will* evolve
over the next few windows. It answers, in order:

**What is happening now? → What attack stage is developing? → What could happen next? → Why does the AI forecast this?**

## 2. Team

**NeuroVex** — see the placeholder team list at the end of this README.

## 3. Event

Built for **Smart India Hackathon 2026**.

## 4. One-line description

Temporal World Model over network states that forecasts attack progression,
not just a "attack / no-attack" classifier.

## 5. Problem statement

Real attacks are **multi-stage** — reconnaissance → scanning → initial access →
… → command & control → exfiltration. Traditional IDS/IPS answers *"is this
suspicious now?"*. Security teams also need *"what is likely to happen next?"*.
ThreatPulse learns the temporal structure of network states and forecasts the
next stages, with a model-confidence estimate and an explanation.

## 6. Why traditional IDS is insufficient here

A classic IDS/ML classifier maps a flow (or PCAP) to a label:

```
Traffic → Detection → Attack / No Attack
```

That is **stateless** and **reactive**. It cannot say the network is *drifting
toward* initial access. ThreatPulse is **stateful and temporal**:

```
Live Traffic → Network Telemetry → Time-Windowed States → Temporal World Model
            → Future-State Simulation → Attack-Progression Forecast → Explainable SOC view
```

## 7. Core innovation — the Temporal World Model

The model learns `P(S[t+k] | S[t-n], …, S[t])`: given recent network-state
history, predict the next state(s). A **next-state head** enables **K-step
autoregressive rollout** (predict S(t+1), feed it back, predict S(t+2)…), which
produces a **future risk timeline** and a **forecast stage**. This is the
project's central idea — not a per-packet classifier.

## 8. Architecture

```
KALI (attacker)  --lab traffic-->  UBUNTU (victim + sensors + AI)
                                     |            |
                                    ZEEK       SURICATA
                                 (conn.log)   (eve.json)
                                     \\          /
                                    Redis Streams (telemetry:zeek / telemetry:suricata)
                                          |
                                   Feature Engine  (10-second windows)
                                          |
                                   Network State S(t)  +  State History [S(t-9)..S(t)]
                                          |
                                   LSTM World Model (PyTorch, multi-head)
                                     /        |         \\
                              Next-State    Risk     Attack-Stage
                                     \\        |         /
                                   K-Step Rollout -> Future Risk Timeline
                                          |
                                   Explainability (grad×input / SHAP-optional)
                                          |
                                   MITRE ATT&CK mapper (potential context)
                                          |
                                   FastAPI  (REST + WebSocket /ws/live)
                                          |
                                   React SOC Dashboard  (viewed on Windows)
```

See `docs/architecture.md` for the full diagram and per-component rationale.

## 9. Live data flow

```
Kali action → Ubuntu receives traffic → Zeek/Suricata log it →
collectors normalize → Redis stream → feature engine (10s window) →
network state → LSTM → forecast (risk / stage / timeline / explanation) →
FastAPI → WebSocket push → dashboard updates LIVE (no refresh).
```

## 10. Repository structure

```
network-attack-forecaster/
├── core/            # config, feature/stage/MITRE schema, events, event bus, logging
├── configs/         # config.yaml, feature_schema.yaml, stage_labels.yaml, mitre_map.yaml
├── features/        # feature engine: network_features, aggregation, normalization, state_builder
├── ml/
│   ├── models/          # lstm_world_model.py (multi-head LSTM)
│   ├── preprocessing/   # synthetic generator, dataset (CSV) adapters
│   ├── training/        # train_lstm.py, train_baseline.py
│   ├── inference/       # forecaster.py (load + K-step rollout), explain.py (attribution)
│   └── evaluation/      # evaluate.py (LSTM vs baseline, report)
├── sensor/
│   ├── collectors/      # base tailer, zeek_collector, suricata_collector
│   ├── zeek/            # install/run notes
│   └── suricata/        # install/run notes
├── replay/          # synthetic_generator.py (same bus path), pcap_replay.py
├── backend/
│   ├── ingestion/       # feature_engine service (bus -> windows -> states)
│   ├── services/        # shared_state, pipeline (continuous inference loop)
│   ├── websocket/       # connection manager + broadcaster
│   ├── api/             # REST routes
│   └── main.py          # FastAPI app + lifespan (mode-driven sources)
├── frontend/        # React + Vite + Tailwind + Recharts SOC dashboard
├── data/            # raw/ processed/ samples/ (tiny sample CSV only)
├── models/          # trained artifacts (.pt/.pkl/.json) — gitignored
├── artifacts/       # evaluation/ output
├── scripts/         # run_all.sh/.ps1, train.sh/.ps1
├── docker/          # backend + frontend Dockerfiles
├── docs/            # architecture, setup_guide, demo_runbook, kali_attack_steps, troubleshooting
├── tests/           # pytest suite (runs without Kali/Zeek/Suricata)
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── README.md  ·  SECURITY.md  ·  .gitignore
```

## 11. Technologies

Python · NumPy · Pandas · scikit-learn · **PyTorch (LSTM)** · FastAPI ·
Uvicorn · WebSockets · **Redis Streams** (with in-memory fallback) · **Zeek** ·
**Suricata** · React · Vite · Tailwind CSS · Recharts.

**Why each (one line):**
- **Redis Streams** — decouples telemetry producers from feature processing while keeping the MVP lightweight.
- **LSTM** — models temporal dependencies between network states with modest compute.
- **WebSocket** — continuous dashboard updates without browser polling/refresh.
- **10-second windows** — convert high-volume event streams into manageable temporal network states.
- **FastAPI** — async REST + WebSocket in one lightweight process.

## 12. Hardware / software requirements

- Windows host with VirtualBox; ~8 GB RAM is enough (CPU-only inference).
- VMs: **Kali Linux** (attacker) and **Ubuntu Server** (victim + sensors + AI).
- Python 3.10–3.12, Node.js 18+.
- Redis optional (an in-memory bus is used automatically if Redis is absent).

## 13. Windows setup (dashboard host)

Windows only needs a **browser** and, for development, **VS Code + Git**.
You open the dashboard at `http://<UBUNTU_IP>:5173`. Optionally run the whole
stack on Windows in replay mode for development (see §25).

## 14. Ubuntu setup (main machine)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git redis-server
git clone <YOUR_REPO_URL> network-attack-forecaster
cd network-attack-forecaster
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# CPU-only torch (smaller):  pip install torch --index-url https://download.pytorch.org/whl/cpu
```

## 15. Kali setup (attacker)

Kali ships with the tools used here. Confirm:
```bash
which nmap curl nc
ip addr            # note the host-only IP
```
Only ever target the configured Ubuntu lab IP. See `docs/kali_attack_steps.md`.

## 16. VirtualBox networking

Give **both** VMs two adapters:
- **Adapter 1 = NAT** — internet for package installs/updates.
- **Adapter 2 = Host-Only** — the isolated lab/attack network.

Find the host-only IPs with `ip addr` on each VM and put them in `.env`
(`KALI_IP`, `UBUNTU_IP`, `MONITOR_INTERFACE`). Never hard-code IPs in code.
Full walkthrough: `docs/setup_guide.md`.

## 17. Zeek install / configure

See `sensor/zeek/README.md`. Summary:
```bash
sudo apt install -y zeek
sudo zeek -i <host-only-iface>      # writes conn.log
```
Set `ZEEK_LOG_DIR` in `.env` to the directory containing `conn.log`.

## 18. Suricata install / configure

See `sensor/suricata/README.md`. Summary:
```bash
sudo apt install -y suricata && sudo suricata-update
sudo suricata -i <host-only-iface> -l /var/log/suricata
```
Set `SURICATA_EVE_PATH=/var/log/suricata/eve.json` in `.env`.

## 19. Redis install

```bash
sudo apt install -y redis-server
sudo systemctl enable --now redis-server
redis-cli ping        # -> PONG
```
Redis is **optional**: if it is unreachable, ThreatPulse automatically uses an
in-process in-memory bus with identical semantics (great for a laptop demo).

## 20. Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 21. Node.js / React setup

```bash
cd frontend
npm install
```

## 22. `.env` setup

```bash
cp .env.example .env
# edit .env: set SYSTEM_MODE, KALI_IP, UBUNTU_IP, MONITOR_INTERFACE, sensor paths
```
Every variable overrides a default in `configs/config.yaml`. Blank = default.
Never commit `.env`.

## 23. Model training

```bash
python -m ml.training.train_lstm            # trains, evaluates, saves artifacts
# or the whole pipeline (LSTM + baseline + evaluation):
./scripts/train.sh                          # Windows: .\scripts\train.ps1
```
Artifacts saved to `models/`: `lstm_world_model.pt`, `scaler.pkl`,
`stage_labels.json`, `feature_schema.json`, `training_metadata.json`.

## 24. Synthetic training

If no dataset is configured, training uses the built-in **synthetic generator**
(`ml/preprocessing/synthetic.py`) which produces realistic staged episodes.
The resulting model's metadata is stamped `training_dataset: synthetic` and the
dashboard shows a **SYNTHETIC** badge. Synthetic metrics are **not** real-world
validation — this is stated honestly everywhere.

To train on a public dataset instead (CIC-IDS2018 / CTU-13 style flow CSV):
```bash
DATASET_PATH=/path/to/flows.csv python -m ml.training.train_lstm
```
(Adjust the column map in `ml/preprocessing/datasets.py` if headers differ.)

## 25. Replay mode

Replay streams synthetic telemetry onto the **same** Redis streams the live
collectors use — so the entire pipeline and dashboard are identical to live
mode. Ideal when Kali/Zeek/Suricata aren't available.

```bash
# whole stack, replay:
./scripts/run_all.sh                        # Windows: .\scripts\run_all.ps1
# or just the generator against a running backend/Redis:
python -m replay.synthetic_generator
```
Set `SYSTEM_MODE=replay` (default). The dashboard shows a **DEMO/REPLAY** badge.

## 26. Live mode

```bash
# .env: SYSTEM_MODE=live  (+ Zeek/Suricata running, paths set)
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
Collectors tail the live logs and feed the same pipeline. `hybrid` runs live
sensors **and** replay together.

## 27. Starting the backend

```bash
source .venv/bin/activate
python -m backend.main
# or: uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## 28. Starting the frontend

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

## 29. Opening the dashboard from Windows

Point the frontend at the Ubuntu backend (frontend `.env`):
```
VITE_BACKEND_URL=http://<UBUNTU_IP>:8000
VITE_WS_URL=ws://<UBUNTU_IP>:8000/ws/live
```
Then browse to `http://<UBUNTU_IP>:5173` from Windows.

## 30. Kali lab attack steps

Authorized, non-destructive telemetry generation only, against the configured
Ubuntu lab IP. See `docs/kali_attack_steps.md`. Examples:
```bash
ping <UBUNTU_IP>
nmap <UBUNTU_IP>
nmap -sV <UBUNTU_IP>
curl http://<UBUNTU_IP>/
nc -vz <UBUNTU_IP> 22
```

## 31. Expected dashboard behavior

At rest: **NORMAL**, **LOW forecast risk**, stage **Normal**. When Kali begins
recon/scanning, within the next 10-second windows the events table fills, the
network state changes, forecast risk rises, the stage advances, the explanation
bars update, and the future-risk timeline bends upward — **without a refresh**.

## 32. How telemetry becomes features

Collectors normalize Zeek/Suricata records into one event schema
(`core/events.py`). The feature engine (`features/network_features.py`)
aggregates a window's events into ~20 named features (connections, unique
ports, SYN/RST counts and ratios, failure rate, destination diversity, alert
counts, …). Feature definitions live in `configs/feature_schema.yaml`; the
state-vector length is derived from it (never hard-coded).

## 33. How 10-second states work

`features/aggregation.py` closes a window every `WINDOW_SECONDS` (default 10).
Each closed window → one feature vector → one **network state S(t)**. States are
pushed into a fixed-length history buffer (`SEQUENCE_LENGTH`, default 10).

## 34. How the LSTM World Model works

`ml/models/lstm_world_model.py`: a shared LSTM encoder over the state sequence,
then three heads — **next-state** (regression), **risk** (sigmoid), **attack
stage** (softmax). The next-state head is what makes forward simulation
possible.

## 35. How K-step forecasting works

`ml/inference/forecaster.py` runs the encoder on `[S(t-9)..S(t)]`, predicts
S(t+1), appends it, and repeats for `FORECAST_HORIZON` steps (default 4 →
+10s..+40s). Each step yields a risk value → the **future risk timeline**. All
values come from the model; none are hard-coded.

## 36. Risk forecast

Risk is the model's sigmoid output, labeled LOW / GUARDED / ELEVATED / HIGH.
The UI always states: *"Model confidence is the model's own confidence, not
certainty that an attack will happen."*

## 37. Attack-stage prediction

The stage head outputs a probability over the 10 stages in
`configs/stage_labels.yaml` (Normal → Exfiltration). The argmax is the current
stage; the rollout's final step gives the forecast stage.

## 38. SHAP / explainability

`ml/inference/explain.py` uses **gradient × input** attribution on the risk head
(fast, CPU-friendly, exact for the live model). SHAP is an optional dependency;
gradient attribution is the default so the live loop stays light. Contributions
are **signed** (positive pushes risk up). Explanations are model-internal, not
proof of intent.

## 39. MITRE ATT&CK mapping

`configs/mitre_map.yaml` maps each stage to **potential** ATT&CK tactics/
techniques (e.g. Scanning → T1046 Network Service Discovery). The UI labels
these "Potential ATT&CK mapping" / "Behavior consistent with…"; a feature never
"proves" a technique.

## 40. Baseline model

`ml/training/train_baseline.py` trains a **non-temporal** LogisticRegression on
the **last** state only, so the temporal LSTM can be compared against a model
that sees no history. This demonstrates whether temporal information helps
(it should, modestly) — we never claim LSTM is universally superior.

## 41. Evaluation

`ml/evaluation/evaluate.py` writes `artifacts/evaluation/evaluation_report.{json,md}`:
stage accuracy/precision/recall/F1, risk MAE/RMSE, next-state MAE/RMSE, binary
ROC-AUC, confusion matrix, forecast-horizon degradation, and the LSTM-vs-baseline
delta. Synthetic runs are stamped SYNTHETIC.

## 42. API documentation

Base: `http://<host>:8000`

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness, pipeline/bus/model status |
| GET | `/api/config` | app config, feature labels, stage list |
| GET | `/api/network/status` | status, hosts, connections, events/s, sensors |
| GET | `/api/risk` | current risk + future risk timeline |
| GET | `/api/forecast` | current + forecast stage, distribution |
| GET | `/api/attack-stage` | stage + potential MITRE mappings |
| GET | `/api/explanations` | signed top feature contributions |
| GET | `/api/events?limit=50` | recent normalized telemetry |
| GET | `/api/model` | model availability + training metadata |
| POST | `/api/model/reload` | hot-reload artifacts after training |

If `API_KEY` is set in `.env`, REST (except `/api/health`) requires header
`X-API-Key: <value>`. Interactive docs at `/docs`.

## 43. WebSocket documentation

`ws://<host>:8000/ws/live` — the backend pushes a full snapshot ~1×/second and
immediately on connect. Payload fields: `timestamp, network_status, mode,
current_state, risk, risk_label, current_stage, forecast_stage,
future_risk_timeline, top_features, recent_events, model_confidence,
sensor_status, model_status, dataset_type, potential_mitre_mappings,
active_hosts, active_connections, events_per_sec, disclaimer`. The client
auto-reconnects with backoff and never crashes on a missing field.

## 44. Troubleshooting

See `docs/troubleshooting.md` (Redis, Zeek/Suricata logs, CORS, WebSocket,
model-not-trained, VirtualBox connectivity).

## 45. Security / lab isolation

See `SECURITY.md`. **All offensive testing must remain inside the isolated,
authorized VirtualBox lab.** Never target real or external systems. Redis is
not exposed publicly; secrets live in `.env` (never committed); CORS is
restricted; the dashboard executes no arbitrary commands.

## 46. Limitations

- The bundled model is **synthetic-trained** by default — a demonstrable
  bootstrap, **not** validated on real traffic. Retrain on a public dataset for
  meaningful metrics.
- Feature set is intentionally compact (MVP); the schema is built to expand.
- Forecasts are probabilistic model outputs, **not guarantees**.
- Single-sensor host (Ubuntu). No multi-node scaling in the MVP.

## 47. Future roadmap

Suricata rule tuning · richer features (TTL, retransmissions, port-scan score) ·
Transformer/Temporal-GNN world models · per-host risk attribution · true SHAP
on batched states · Kafka/scale-out if needed · model comparison dashboard.

## 48. GitHub

Repository: `<ADD-YOUR-GITHUB-URL-HERE>`

## 49. Team members

Team **NeuroVex** — SIH 2026
- `<Member 1 — role>`
- `<Member 2 — role>`
- `<Member 3 — role>`
- `<Member 4 — role>`
- `<Member 5 — role>`
- `<Member 6 — role>`

---

### Quick start (replay demo, one command)

```bash
cp .env.example .env
./scripts/run_all.sh            # Windows: .\scripts\run_all.ps1
# Dashboard: http://localhost:5173   API: http://localhost:8000   WS: ws://localhost:8000/ws/live
```

> ThreatPulse is a decision-support prototype. A forecast is a model
> prediction, not a certainty. Use only inside an authorized isolated lab.

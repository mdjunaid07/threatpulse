# Demo Runbook (repeatable)

A controlled, repeatable demonstration for judges. Two variants: **Live**
(Kali→Ubuntu) and **Replay** (backup, no lab hardware). Have the replay path
ready as insurance.

## What judges should watch

1. Kali generates controlled activity.
2. Ubuntu's sensors observe it (events appear in the table).
3. The **network state** changes (summary cards move).
4. The **World Model** forecast reacts: risk rises, stage advances, the future
   risk timeline bends up, explanation bars change.
5. The **MITRE** panel shows *potential* mappings.
6. All of this updates **without a browser refresh**.

Keep repeating the line: *forecast = model prediction, not a guarantee.*

---

## LIVE variant

### T-5 min — bring up Ubuntu services
```bash
# terminal 1 (sensor)
sudo zeek -i <MONITOR_INTERFACE>
# terminal 2 (sensor)
sudo suricata -i <MONITOR_INTERFACE> -l /var/log/suricata
# terminal 3 (app)
source .venv/bin/activate
python -m backend.main            # SYSTEM_MODE=live in .env
# terminal 4 (frontend)
cd frontend && npm run dev -- --host 0.0.0.0 --port 5173
```

### T-3 min — open the dashboard (Windows)
Browse to `http://<UBUNTU_IP>:5173`. Confirm top bar shows **LIVE** (green),
Mode LIVE, Model TRAINED.

### T-2 min — verify NORMAL
Summary cards: Network Status **NORMAL**, Forecast Risk **LOW**, stage
**Normal**. Sensor health: Zeek/Suricata/Redis/Model green.

### T-1 min — verify model loaded
`curl http://<UBUNTU_IP>:8000/api/model` → `"available": true`.

### T=0 — Kali begins reconnaissance
```bash
nmap -sn <UBUNTU_IP>
```

### T+10s — telemetry change
Live events table fills; active connections/events-per-sec rise.

### T+20s — scanning becomes visible
```bash
nmap <UBUNTU_IP>
```
Stage indicator moves toward **Scanning**; explanation bars show SYN ratio /
port diversity / failure rate increasing.

### T+30s — forecast changes
Future risk timeline bends upward (Now < +10s < +20s …). Risk label climbs
LOW → GUARDED → ELEVATED.

### T+40s — potential next stage
```bash
nmap -sV <UBUNTU_IP>
```
Forecast stage may advance (e.g. Scanning → Initial Access-related), MITRE panel
shows potential techniques (e.g. T1046).

### Wind down
Stop Kali activity; over subsequent windows the risk decays back toward NORMAL
— demonstrating the system is reacting to live telemetry, not scripted values.

---

## REPLAY variant (backup)

```bash
cp .env.example .env       # SYSTEM_MODE=replay (default)
./scripts/run_all.sh       # Windows: .\scripts\run_all.ps1
# open http://localhost:5173
```
The synthetic generator walks NORMAL → RECON → SCANNING → INCREASED CONNECTIONS
→ INITIAL-ACCESS-related through the **same** pipeline. The dashboard shows a
**DEMO/REPLAY** badge so it's clear this is synthetic. Everything else looks
identical to live mode.

## If something breaks mid-demo

- Dashboard not LIVE → check backend is up (`/api/health`) and
  `VITE_WS_URL` points at the right host; the client auto-reconnects.
- No events in live mode → confirm Zeek/Suricata are writing logs and the paths
  in `.env` are correct; switch to the replay variant as a fallback.
- See `docs/troubleshooting.md`.

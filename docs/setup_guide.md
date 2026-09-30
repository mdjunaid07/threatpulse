# Setup Guide (beginner-friendly)

This assumes you have a Windows host, VirtualBox, a Kali VM, and an Ubuntu
Server VM. It explains everything from networking to running the dashboard. No
prior Zeek/Redis/WebSocket/LSTM knowledge required.

> **Fastest path (no VMs):** you can run the whole thing in **replay mode** on a
> single machine (even Windows) to see it work — jump to §O. The VM steps below
> are for the full live Kali→Ubuntu demo.

---

## A. VirtualBox networking

Each VM gets two network adapters:

1. **Adapter 1 — NAT**: gives the VM internet (for `apt install`). Enabled by
   default.
2. **Adapter 2 — Host-Only Adapter**: the private lab network Kali and Ubuntu
   share.

To add Host-Only:
1. VirtualBox → **File ▸ Host Network Manager ▸ Create** (makes e.g.
   `vboxnet0`, network like `192.168.56.0/24`).
2. For **each** VM: **Settings ▸ Network ▸ Adapter 2 ▸ Enable ▸ Attached to:
   Host-Only Adapter ▸** pick `vboxnet0`.

Why: the Host-Only network isolates all attack traffic from your real network.

## B. Finding IP addresses

Boot both VMs. On each:
```bash
ip addr
```
Look for the interface on the host-only subnet (e.g. `192.168.56.x`). Common
names: `enp0s8`, `eth1`. Note:
- `UBUNTU_IP` = Ubuntu's host-only IP
- `KALI_IP` = Kali's host-only IP
- `MONITOR_INTERFACE` = Ubuntu's host-only interface name (e.g. `enp0s8`)

## C. Testing Kali → Ubuntu connectivity

On Kali:
```bash
ping <UBUNTU_IP>
```
If replies come back, the lab network works. If not, recheck Adapter 2 on both
VMs and that they share the same host-only network.

## D. Installing Ubuntu dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git redis-server
```

## E. Installing Zeek

```bash
sudo apt install -y zeek        # or follow zeek.org for the LTS repo
# if installed under /opt/zeek:
echo 'export PATH=$PATH:/opt/zeek/bin' >> ~/.bashrc && source ~/.bashrc
zeek --version
```
More detail: `sensor/zeek/README.md`.

## F. Installing Suricata

```bash
sudo apt install -y suricata
sudo suricata-update            # needs internet (NAT adapter)
```
More detail: `sensor/suricata/README.md`.

## G. Configuring interfaces

Decide which interface the sensors watch — the **host-only** one from §B
(e.g. `enp0s8`). You'll pass it to Zeek/Suricata with `-i enp0s8` and set
`MONITOR_INTERFACE=enp0s8` in `.env`.

## H. Installing Redis

```bash
sudo apt install -y redis-server
sudo systemctl enable --now redis-server
redis-cli ping     # -> PONG
```
Optional: if you skip Redis, ThreatPulse uses an in-memory bus automatically.

## I. Installing Python (project env)

```bash
cd network-attack-forecaster
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# CPU-only torch (smaller): pip install torch --index-url https://download.pytorch.org/whl/cpu
```

## J. Installing Node (frontend)

```bash
# Node 18+ (nvm recommended)
cd frontend && npm install && cd ..
```

## K. Starting the backend

```bash
cp .env.example .env      # then edit IPs/interface/paths
source .venv/bin/activate
python -m ml.training.train_lstm     # one-off: create the model
python -m backend.main               # starts API + inference loop
# health check:
curl http://localhost:8000/api/health
```

## L. Starting the frontend

```bash
cd frontend
# point it at the backend (edit frontend/.env or export):
#   VITE_BACKEND_URL=http://<UBUNTU_IP>:8000
#   VITE_WS_URL=ws://<UBUNTU_IP>:8000/ws/live
npm run dev -- --host 0.0.0.0 --port 5173
```

## M. Connecting the Windows browser

On Windows open: `http://<UBUNTU_IP>:5173`. You should see the top bar go
**LIVE** (green) once the WebSocket connects.

## N. Training the model

```bash
./scripts/train.sh        # trains LSTM + baseline, writes evaluation report
# Windows: .\scripts\train.ps1
```
Report: `artifacts/evaluation/evaluation_report.md`.

## O. Starting replay (no lab hardware needed)

```bash
cp .env.example .env       # SYSTEM_MODE=replay is the default
./scripts/run_all.sh       # Windows: .\scripts\run_all.ps1
# open http://localhost:5173
```
This runs backend + frontend and streams synthetic telemetry through the real
pipeline. Great for development or as a demo backup.

## P. Starting live mode

Edit `.env`:
```
SYSTEM_MODE=live
UBUNTU_IP=<...>
KALI_IP=<...>
MONITOR_INTERFACE=enp0s8
ZEEK_LOG_DIR=/opt/zeek/logs/current
SURICATA_EVE_PATH=/var/log/suricata/eve.json
```
Start Zeek and Suricata on the monitor interface (separate terminals), then
start the backend and frontend as above.

## Q. Running controlled Kali activity

On Kali (only against `<UBUNTU_IP>`): see `docs/kali_attack_steps.md`.
```bash
nmap <UBUNTU_IP>
```

## R. Watching the dashboard

Within the next 10-second windows you should see events appear, network state
change, forecast risk rise, and the attack stage advance — **no refresh**.

## S. Troubleshooting

See `docs/troubleshooting.md`.

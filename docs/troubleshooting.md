# Troubleshooting

Quick fixes for the most common issues. Commands assume the repo root with the
Python venv activated.

## Diagnostics first
```bash
curl http://localhost:8000/api/health        # pipeline/bus/model/mode
curl http://localhost:8000/api/model          # model availability + metadata
```
`bus_backend` tells you whether Redis or the in-memory fallback is in use.

## Dashboard shows DISCONNECTED / not LIVE
- Backend not running → start it: `python -m backend.main`.
- Wrong URL → set `VITE_WS_URL=ws://<UBUNTU_IP>:8000/ws/live` and
  `VITE_BACKEND_URL=http://<UBUNTU_IP>:8000` in `frontend/.env`, restart `npm run dev`.
- Firewall → allow ports 8000 (backend) and 5173 (frontend) on Ubuntu.
- The client auto-reconnects with backoff; give it a few seconds.

## "Model: NOT TRAINED"
```bash
python -m ml.training.train_lstm
curl -X POST http://localhost:8000/api/model/reload   # hot-reload without restart
```

## Redis
```bash
redis-cli ping            # expect PONG
sudo systemctl status redis-server
```
If Redis is down the app **still runs** on the in-memory bus (health shows
`bus_backend: memory`). For a multi-process demo (separate replay + backend),
run Redis so they share streams; within one process the in-memory bus is fine.

## No live events (live mode)
- Confirm Zeek is writing `conn.log`:
  ```bash
  ls -l $ZEEK_LOG_DIR/conn.log
  tail -f $ZEEK_LOG_DIR/conn.log
  ```
- Confirm Suricata EVE exists:
  ```bash
  tail -f /var/log/suricata/eve.json
  ```
- Ensure sensors watch the **host-only** interface (`-i <MONITOR_INTERFACE>`).
- Ensure `.env` paths (`ZEEK_LOG_DIR`, `SURICATA_EVE_PATH`) match reality.
- Generate traffic from Kali (`nmap <UBUNTU_IP>`).
- As a fallback, switch to `SYSTEM_MODE=replay`.

## Zeek `conn.log` format
Both TSV (default) and JSON logs are supported. If you enabled JSON logs, the
collector detects it automatically. Make sure you point at the directory that
actually contains the current `conn.log` (with `zeekctl` it's usually
`/opt/zeek/logs/current`).

## CORS errors in the browser console
Add your dashboard origin to `security.cors_origins` in `configs/config.yaml`
or set `FRONTEND_ORIGIN` in `.env`, then restart the backend.

## 401 on REST calls
You set `API_KEY` in `.env`. Send the header `X-API-Key: <value>` (or clear
`API_KEY` for open dev access). `/api/health` is always open.

## Kali can't reach Ubuntu
- Both VMs need **Adapter 2 = Host-Only** on the **same** host-only network.
- Check `ip addr` on each; they must be on the same subnet.
- `ping <UBUNTU_IP>` from Kali; if it fails, recheck adapters and that Ubuntu's
  firewall isn't blocking ICMP.

## Torch install is slow / large
Use the CPU wheel:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

## Frontend build warning about chunk size
Harmless for the demo (Recharts is large). Ignore, or code-split later.

## Tests
```bash
python -m pytest -q       # runs without Kali/Zeek/Suricata/Redis
```

## Ports in use
Change `APP_PORT` in `.env` (backend) and the Vite `--port` (frontend), and
update the frontend `VITE_*` URLs to match.

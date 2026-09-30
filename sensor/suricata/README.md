# Suricata — IDS telemetry source

Suricata produces `eve.json` (EVE JSON) with `alert` and `flow` events.
ThreatPulse tails it (`sensor/collectors/suricata_collector.py`) and turns
alerts into telemetry the feature engine counts (alert_count / severity).

Suricata is a SENSOR, not the forecasting model — the LSTM World Model remains
the core. If Suricata is absent the app keeps running on Zeek/replay telemetry.

## Install (Ubuntu)
```bash
sudo apt update && sudo apt install -y suricata
sudo suricata-update            # fetch rules (needs internet / NAT adapter)
```

## Run against the lab interface
```bash
# Enable eve.json in /etc/suricata/suricata.yaml (outputs -> eve-log -> enabled: yes)
sudo suricata -i enp0s8 -l /var/log/suricata
```

Point the app at the EVE file in `.env`:
```
SURICATA_ENABLED=true
SURICATA_EVE_PATH=/var/log/suricata/eve.json
```

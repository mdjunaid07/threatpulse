# Zeek — telemetry source

Zeek watches the Ubuntu VM's monitoring interface and writes structured logs
(`conn.log`, `dns.log`, `http.log`, `ssl.log`). ThreatPulse tails `conn.log`
(`sensor/collectors/zeek_collector.py`) and normalizes each connection into a
telemetry event on the bus.

## Install (Ubuntu)
```bash
# Zeek LTS via the official OpenSUSE build repo (see docs/setup_guide.md for
# the current key/URL). Then:
sudo apt update && sudo apt install -y zeek
echo 'export PATH=$PATH:/opt/zeek/bin' >> ~/.bashrc && source ~/.bashrc
```

## Run against the lab interface
```bash
# Find your host-only interface with: ip addr   (e.g. enp0s8)
sudo zeek -i enp0s8 LogAscii::use_json=F
# logs appear in the working dir, or /opt/zeek/logs/current when run via zeekctl
```

Point the app at the log directory in `.env`:
```
ZEEK_ENABLED=true
ZEEK_LOG_DIR=/opt/zeek/logs/current   # or the dir where conn.log is written
```

Both TSV (default) and JSON Zeek logs are supported by the collector.

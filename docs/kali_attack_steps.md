# Kali Lab Activity Guide (authorized, non-destructive)

> **Scope rule:** every command here targets **only** the Ubuntu lab VM at
> `<UBUNTU_IP>` on the isolated host-only network you own. Never point these at
> any other host. See `SECURITY.md`.

The goal is to generate **observable telemetry** so Zeek/Suricata produce
events, the feature engine's network state changes, and the World Model's
forecast responds. These are ordinary discovery/probe activities — no
exploitation, persistence, credential theft, or payloads.

## 0. Confirm the target and connectivity

```bash
ip addr                      # confirm your KALI_IP (host-only)
ping -c 3 <UBUNTU_IP>        # confirm you can reach the victim
```
Expected telemetry: a few ICMP/benign connections → **NORMAL**, low risk.

## 1. Host discovery

```bash
nmap -sn <UBUNTU_IP>         # ping scan / host discovery
```
Expected: small burst of connections; recon-like signal begins.

## 2. Port scan (the key demo step)

```bash
nmap <UBUNTU_IP>             # default TCP SYN scan of common ports
```
Expected telemetry:
- many **unique destination ports**
- **SYN-heavy** traffic, many half-open / failed connections
- rising **connection_failure_rate** and **dst_diversity**
- Zeek `conn.log` rows with states like `S0`/`REJ`
- Suricata scan-related alerts (if rules match)
→ Dashboard: stage moves toward **Scanning**, forecast risk rises.

## 3. Service/version enumeration

```bash
nmap -sV <UBUNTU_IP>         # probe service versions on open ports
```
Expected: more sustained connections to specific open ports; service-targeting
signal. → possible **Initial Access-related** forecast if the model has learned
that progression.

## 4. Simple service probes

```bash
curl -i http://<UBUNTU_IP>/           # if a web service is running
nc -vz <UBUNTU_IP> 22                 # TCP connect check to a port
nc -vz <UBUNTU_IP> 80
```
Expected: targeted connections to individual services.

## 5. Repeated connection attempts (elevated activity)

```bash
for p in 21 22 23 25 80 443 3306 8080; do nc -vz -w1 <UBUNTU_IP> $p; done
```
Expected: a cluster of connection attempts across services → increased
destination diversity and failures within the window.

---

## What each activity should produce (summary)

| Kali activity | Feature signals | Likely stage signal |
|---|---|---|
| ping / `-sn` | few connections | Normal → Reconnaissance |
| `nmap` | many dst ports, SYN, failures | Scanning |
| `nmap -sV` | service-targeted conns | Initial Access-related |
| curl / nc probes | targeted conns | Reconnaissance/Scanning |

**Reminder:** forecast values are the **model's predictions**, not guarantees.
The dashboard states this explicitly. Stop activity and observe the risk decay
back toward NORMAL over subsequent windows.

## Not included (by design)

No exploit code, brute-force credential attacks, malware, persistence,
lateral-movement tooling, or evasion. This project is a **defensive forecasting
demo**; Kali is only a controlled telemetry generator.

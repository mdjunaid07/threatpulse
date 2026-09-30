# Security & Responsible Use

ThreatPulse is a **defensive** SOC forecasting prototype for a **Smart India
Hackathon 2026** project by **Team NeuroVex**. It is designed to run inside an
**isolated, authorized VirtualBox lab** only.

## Authorized testing only

- **All offensive activity (Kali) must target ONLY the Ubuntu lab VM you own
  and control, on the isolated host-only network.**
- **Never** run scans, connection floods, or any traffic generation against
  real, external, public, campus, or corporate systems, or any host you are not
  explicitly authorized to test.
- The project intentionally does **not** include and will **not** help with
  destructive payloads, exploitation for compromise, persistence, credential
  theft, malware, or evasion. Kali's role here is limited to generating
  **observable, benign-to-infrastructure telemetry** (discovery, port scans,
  simple HTTP/nc probes) so the sensors and model have something to observe.

## Lab isolation

- Use a VirtualBox **Host-Only** adapter for the attack/monitoring network.
- Keep the host-only network separate from any bridged/production network.
- NAT (if used) is only for package installation/updates on the VMs.

## Application security practices

- **No committed secrets.** Configuration/secrets go in `.env` (gitignored);
  `.env.example` contains no real values.
- **Redis is not publicly exposed.** In Docker it has no host port mapping by
  default; on a VM bind it to localhost / the host-only interface only.
- **CORS is restricted** to the configured frontend origin(s)
  (`security.cors_origins` / `FRONTEND_ORIGIN`).
- **Optional API key**: set `API_KEY` to require `X-API-Key` on REST endpoints.
- **Input validation / safe parsing**: all telemetry is normalized and
  type-coerced (`core/events.py`); malformed events are dropped, never fatal.
- **No arbitrary command execution** from the dashboard or API. The web UI is
  read-only visualization; it cannot launch scans or shell commands.
- **WebSocket**: server pushes only; client messages are ignored. Restrict who
  can reach `:8000`/`:5173` to the lab network. Add a reverse proxy with auth
  if exposing beyond localhost.
- **Least privilege**: run collectors as an unprivileged user tailing logs;
  only Zeek/Suricata capture needs elevated privileges, and only on the lab
  interface.
- **Safe logging**: logs contain lab IPs/ports and event metadata only — no
  secrets. Review before sharing externally.

## Data & model honesty

- Synthetic/replay data is always **clearly labeled**; synthetic metrics are
  never presented as real-world validation.
- If the model is untrained the UI shows **MODEL NOT TRAINED** rather than
  fabricating numbers. Forecast values always come from the model.

## Reporting

This is a student hackathon project. If you find a security issue in the code,
open an issue in the repository (do not include sensitive data in the report).

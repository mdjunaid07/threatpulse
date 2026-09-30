import Panel from "./Panel";

const ORDER = ["zeek", "suricata", "redis", "replay", "model"];
const LABELS = {
  zeek: "Zeek",
  suricata: "Suricata",
  redis: "Redis / Bus",
  replay: "Replay",
  model: "Model",
};

export default function SensorHealth({ snapshot, wsStatus }) {
  const status = snapshot?.sensor_status || {};
  const rows = ORDER.filter((k) => k in status).map((k) => ({
    key: k,
    label: LABELS[k] || k,
    ...describe(k, status[k]),
  }));

  return (
    <Panel title="Sensor & Component Health" className="h-full">
      <ul className="space-y-2">
        <HealthRow label="Dashboard link" ok={wsStatus === "connected"} note={wsStatus} />
        {rows.map((r) => (
          <HealthRow key={r.key} label={r.label} ok={r.ok} note={r.note} />
        ))}
      </ul>
    </Panel>
  );
}

function describe(key, s) {
  if (!s) return { ok: false, note: "unknown" };
  if (key === "redis") return { ok: !!s.ok, note: s.note || s.backend };
  if (key === "model")
    return { ok: !!s.ok, note: s.status === "TRAINED" ? "trained" : "not trained" };
  if (key === "replay")
    return { ok: !!s.ok, note: s.running ? `running · ${s.current_stage}` : "stopped" };
  // collectors (zeek/suricata)
  if (!s.running) return { ok: false, note: "not running" };
  if (!s.present) return { ok: false, note: "log not found (offline)" };
  return { ok: true, note: `tailing · ${s.published} events` };
}

function HealthRow({ label, ok, note }) {
  return (
    <li className="flex items-center justify-between text-xs">
      <span className="flex items-center gap-2">
        <span
          className={`h-2 w-2 rounded-full ${ok ? "bg-soc-green" : "bg-soc-red"}`}
        />
        <span className="text-soc-text">{label}</span>
      </span>
      <span className={`text-[11px] ${ok ? "text-soc-muted" : "text-soc-red"}`}>
        {ok ? note : note || "offline"}
      </span>
    </li>
  );
}

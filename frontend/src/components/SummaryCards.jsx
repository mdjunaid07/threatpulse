import { pct, statusColor, riskLabelColor } from "../lib/format";

export default function SummaryCards({ snapshot }) {
  const s = snapshot || {};
  const cards = [
    {
      label: "Network Status",
      value: s.network_status || "—",
      valueClass: statusColor(s.network_status),
    },
    {
      label: "Active Hosts",
      value: s.active_hosts ?? 0,
    },
    {
      label: "Active Connections",
      value: s.active_connections ?? 0,
    },
    {
      label: "Events / sec",
      value: s.events_per_sec ?? 0,
    },
    {
      label: "Forecast Risk",
      value: s.model_status === "TRAINED" ? pct(s.risk) : "N/A",
      valueClass: s.model_status === "TRAINED" ? riskLabelColor(s.risk_label) : "text-soc-muted",
      sub: s.model_status === "TRAINED" ? s.risk_label : "model not trained",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
      {cards.map((c) => (
        <div
          key={c.label}
          className="bg-soc-panel border border-soc-border rounded-xl px-4 py-3"
        >
          <p className="text-[10px] uppercase tracking-wider text-soc-muted">
            {c.label}
          </p>
          <p className={`text-2xl font-bold mt-1 ${c.valueClass || "text-soc-text"}`}>
            {c.value}
          </p>
          {c.sub && (
            <p className="text-[10px] text-soc-muted mt-0.5">{c.sub}</p>
          )}
        </div>
      ))}
    </div>
  );
}

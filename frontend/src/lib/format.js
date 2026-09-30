// Small presentation helpers shared across dashboard components.

export function riskColor(risk) {
  if (risk >= 0.75) return "#EF4444"; // red
  if (risk >= 0.5) return "#F59E0B"; // amber
  if (risk >= 0.25) return "#EAB308"; // yellow-ish
  return "#22C55E"; // green
}

export function riskLabelColor(label) {
  switch ((label || "").toUpperCase()) {
    case "HIGH":
      return "text-soc-red";
    case "ELEVATED":
      return "text-soc-amber";
    case "GUARDED":
      return "text-yellow-400";
    case "LOW":
      return "text-soc-green";
    default:
      return "text-soc-muted";
  }
}

export function statusColor(status) {
  switch ((status || "").toUpperCase()) {
    case "SUSPICIOUS":
    case "MODEL NOT TRAINED":
      return "text-soc-red";
    case "ELEVATED":
      return "text-soc-amber";
    case "GUARDED":
      return "text-yellow-400";
    case "NORMAL":
      return "text-soc-green";
    default:
      return "text-soc-muted";
  }
}

export function pct(x) {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  return `${(x * 100).toFixed(0)}%`;
}

export function fmtTime(ts) {
  if (!ts) return "—";
  const d = new Date(typeof ts === "number" ? ts * 1000 : ts);
  return d.toLocaleTimeString([], { hour12: false });
}

export function severityColor(sev) {
  // Suricata: 1 high .. 3 low
  if (sev === 1) return "text-soc-red";
  if (sev === 2) return "text-soc-amber";
  if (sev === 3) return "text-soc-muted";
  return "text-soc-muted";
}

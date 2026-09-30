import Panel from "./Panel";
import { fmtTime, severityColor } from "../lib/format";

export default function EventsTable({ snapshot }) {
  const events = snapshot?.recent_events || [];

  return (
    <Panel
      title="Live Network Events"
      subtitle="Normalized telemetry from Zeek / Suricata / replay"
      right={<span className="text-[10px] text-soc-muted">{events.length} shown</span>}
      className="h-full"
    >
      <div className="overflow-auto thin-scroll max-h-72">
        <table className="w-full text-[11px]">
          <thead className="sticky top-0 bg-soc-panel">
            <tr className="text-soc-muted text-left uppercase tracking-wider">
              <th className="py-1.5 pr-2 font-medium">Time</th>
              <th className="py-1.5 pr-2 font-medium">Source</th>
              <th className="py-1.5 pr-2 font-medium">Src → Dst</th>
              <th className="py-1.5 pr-2 font-medium">Port</th>
              <th className="py-1.5 pr-2 font-medium">Proto</th>
              <th className="py-1.5 pr-2 font-medium">Event</th>
            </tr>
          </thead>
          <tbody className="font-mono">
            {events.length === 0 && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-soc-muted font-sans">
                  Waiting for telemetry…
                </td>
              </tr>
            )}
            {events.map((e, i) => (
              <tr key={i} className="border-t border-soc-border/60">
                <td className="py-1 pr-2 text-soc-muted">{fmtTime(e.ts)}</td>
                <td className="py-1 pr-2">
                  <span
                    className={
                      e.source === "suricata"
                        ? "text-soc-amber"
                        : e.source === "replay"
                        ? "text-soc-cyan"
                        : "text-soc-blue"
                    }
                  >
                    {e.source}
                  </span>
                </td>
                <td className="py-1 pr-2 text-soc-text">
                  {short(e.src_ip)} → {short(e.dst_ip)}
                </td>
                <td className="py-1 pr-2 text-soc-muted">{e.dst_port || "—"}</td>
                <td className="py-1 pr-2 text-soc-muted">{e.proto || "—"}</td>
                <td className={`py-1 pr-2 ${e.severity ? severityColor(e.severity) : "text-soc-text"}`}>
                  {e.event}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function short(ip) {
  if (!ip) return "—";
  return ip;
}

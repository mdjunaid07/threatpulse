import { statusColor } from "../lib/format";

export default function TopBar({ snapshot, status }) {
  const mode = snapshot?.mode || "—";
  const modelStatus = snapshot?.model_status || "NOT_TRAINED";
  const dataset = snapshot?.dataset_type;
  const connected = status === "connected";

  return (
    <header className="bg-soc-panel border border-soc-border rounded-xl px-4 py-3 flex flex-wrap items-center gap-x-6 gap-y-2">
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg bg-soc-cyan/15 border border-soc-cyan/40 flex items-center justify-center">
          <span className="text-soc-cyan font-bold text-lg">TP</span>
        </div>
        <div>
          <h1 className="text-base font-bold text-soc-text leading-tight">
            ThreatPulse
          </h1>
          <p className="text-[11px] text-soc-muted leading-tight">
            AI Network Attack Forecasting · Team NeuroVex
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 ml-auto">
        <span
          className={`h-2.5 w-2.5 rounded-full ${
            connected ? "bg-soc-green live-dot" : "bg-soc-red"
          }`}
        />
        <span
          className={`text-xs font-semibold ${
            connected ? "text-soc-green" : "text-soc-red"
          }`}
        >
          {connected ? "LIVE" : status === "connecting" ? "CONNECTING…" : "DISCONNECTED"}
        </span>
      </div>

      <Divider />
      <Meta label="Mode" value={mode.toUpperCase()} highlight={mode === "replay"} />
      <Meta label="Sensor" value="Ubuntu" />
      <Meta label="Model" value="LSTM World Model" />
      <Meta
        label="Model status"
        value={modelStatus === "TRAINED" ? "TRAINED" : "NOT TRAINED"}
        valueClass={modelStatus === "TRAINED" ? "text-soc-green" : "text-soc-red"}
      />
      {dataset && dataset !== "unknown" && (
        <Meta
          label="Trained on"
          value={dataset === "synthetic" ? "SYNTHETIC" : dataset.toUpperCase()}
          valueClass={dataset === "synthetic" ? "text-soc-amber" : "text-soc-text"}
        />
      )}
    </header>
  );
}

function Meta({ label, value, valueClass = "text-soc-text", highlight }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wider text-soc-muted">
        {label}
      </span>
      <span className={`text-xs font-semibold ${valueClass}`}>
        {value}
        {highlight && (
          <span className="ml-1 text-[9px] px-1 py-0.5 rounded bg-soc-amber/20 text-soc-amber align-middle">
            DEMO
          </span>
        )}
      </span>
    </div>
  );
}

function Divider() {
  return <span className="h-8 w-px bg-soc-border hidden sm:block" />;
}

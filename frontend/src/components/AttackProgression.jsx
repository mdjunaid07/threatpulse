import Panel from "./Panel";

// The canonical kill-chain order (matches configs/stage_labels.yaml).
const STAGES = [
  { key: "normal", label: "Normal" },
  { key: "reconnaissance", label: "Reconnaissance" },
  { key: "scanning", label: "Scanning" },
  { key: "initial_access", label: "Initial Access" },
  { key: "execution", label: "Execution" },
  { key: "persistence", label: "Persistence" },
  { key: "privilege_escalation", label: "Privilege Escalation" },
  { key: "lateral_movement", label: "Lateral Movement" },
  { key: "command_and_control", label: "Command & Control" },
  { key: "exfiltration", label: "Exfiltration" },
];

export default function AttackProgression({ snapshot }) {
  const trained = snapshot?.model_status === "TRAINED";
  const currentKey = snapshot?.current_stage?.key || "normal";
  const forecastKey = snapshot?.forecast_stage?.key || "normal";

  return (
    <Panel
      title="Attack Progression"
      subtitle="Observed stage vs. forecast stage"
      className="h-full"
    >
      {!trained ? (
        <p className="text-xs text-soc-muted py-6 text-center">
          Model not trained — stage inference unavailable.
        </p>
      ) : (
        <ol className="relative space-y-0.5">
          {STAGES.map((st, i) => {
            const isCurrent = st.key === currentKey;
            const isForecast = st.key === forecastKey && forecastKey !== currentKey;
            return (
              <li key={st.key} className="flex items-center gap-3">
                <div className="flex flex-col items-center">
                  <span
                    className={`h-3 w-3 rounded-full border ${
                      isCurrent
                        ? "bg-soc-cyan border-soc-cyan"
                        : isForecast
                        ? "bg-transparent border-soc-amber"
                        : "bg-soc-border border-soc-border"
                    }`}
                  />
                  {i < STAGES.length - 1 && (
                    <span className="h-4 w-px bg-soc-border" />
                  )}
                </div>
                <div className="flex items-center gap-2 py-0.5">
                  <span
                    className={`text-xs ${
                      isCurrent
                        ? "text-soc-cyan font-semibold"
                        : isForecast
                        ? "text-soc-amber"
                        : "text-soc-muted"
                    }`}
                  >
                    {st.label}
                  </span>
                  {isCurrent && (
                    <Badge className="bg-soc-cyan/15 text-soc-cyan">observed</Badge>
                  )}
                  {isForecast && (
                    <Badge className="bg-soc-amber/15 text-soc-amber">forecast →</Badge>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Panel>
  );
}

function Badge({ children, className }) {
  return (
    <span className={`text-[9px] uppercase tracking-wide px-1.5 py-0.5 rounded ${className}`}>
      {children}
    </span>
  );
}

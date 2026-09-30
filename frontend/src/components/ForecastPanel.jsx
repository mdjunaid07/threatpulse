import Panel from "./Panel";
import { pct, riskLabelColor } from "../lib/format";

export default function ForecastPanel({ snapshot }) {
  const trained = snapshot?.model_status === "TRAINED";
  const cur = snapshot?.current_stage || {};
  const fc = snapshot?.forecast_stage || {};
  const mitre = snapshot?.potential_mitre_mappings || {};
  const techniques = mitre.techniques || [];

  return (
    <Panel title="Forecast" subtitle="What is happening → what may come next" className="h-full">
      {!trained ? (
        <div className="text-xs text-soc-muted py-4">
          Model not trained. The system is honest about this rather than
          fabricating a forecast. Train it with:
          <code className="block mt-2 bg-soc-panel2 rounded p-2 text-soc-cyan">
            python -m ml.training.train_lstm
          </code>
        </div>
      ) : (
        <div className="space-y-3">
          <Row label="Current state">
            <span className="text-soc-cyan font-semibold">{cur.label || "—"}</span>
          </Row>
          <Row label="Predicted next">
            <span className="text-soc-amber font-semibold">{fc.label || "—"}</span>
          </Row>
          <Row label="Model confidence">
            <span className={riskLabelColor(snapshot?.risk_label)}>
              {(snapshot?.model_confidence ?? 0).toFixed(2)}
            </span>
          </Row>
          <Row label="Forecast risk">
            <span className={riskLabelColor(snapshot?.risk_label)}>
              {pct(snapshot?.risk)} · {snapshot?.risk_label}
            </span>
          </Row>

          <div className="pt-1">
            <p className="text-[10px] uppercase tracking-wider text-soc-muted mb-1">
              Potential MITRE ATT&CK mapping
            </p>
            {mitre.tactic && mitre.tactic !== "N/A" ? (
              <>
                <p className="text-xs text-soc-text">{mitre.tactic}</p>
                <div className="flex flex-wrap gap-1 mt-1">
                  {techniques.map((t) => (
                    <span
                      key={t.id}
                      className="text-[10px] px-1.5 py-0.5 rounded bg-soc-blue/15 text-soc-blue"
                    >
                      {t.id} {t.name}
                    </span>
                  ))}
                </div>
                <p className="text-[10px] text-soc-muted mt-1">{mitre.note}</p>
              </>
            ) : (
              <p className="text-xs text-soc-muted">
                No suspicious progression indicated.
              </p>
            )}
          </div>

          <div className="mt-2 rounded-lg bg-soc-amber/10 border border-soc-amber/30 p-2">
            <p className="text-[10px] text-soc-amber leading-snug">
              {snapshot?.disclaimer ||
                "Model confidence is the model's own confidence, not certainty that an attack will happen."}
            </p>
          </div>
        </div>
      )}
    </Panel>
  );
}

function Row({ label, children }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-soc-muted">{label}</span>
      {children}
    </div>
  );
}

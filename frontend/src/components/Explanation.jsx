import Panel from "./Panel";

export default function Explanation({ snapshot }) {
  const trained = snapshot?.model_status === "TRAINED";
  const feats = snapshot?.top_features || [];
  const maxMag = Math.max(...feats.map((f) => Math.abs(f.contribution || 0)), 1e-6);

  return (
    <Panel
      title="AI Explanation"
      subtitle="Signed feature attribution for the current forecast"
      className="h-full"
    >
      {!trained ? (
        <p className="text-xs text-soc-muted py-6 text-center">
          Model not trained — no attributions.
        </p>
      ) : feats.length === 0 ? (
        <p className="text-xs text-soc-muted py-6 text-center">Warming up…</p>
      ) : (
        <div className="space-y-2.5">
          {feats.map((f) => {
            const mag = Math.abs(f.contribution || 0);
            const width = Math.max(4, (mag / maxMag) * 100);
            const up = (f.contribution || 0) >= 0;
            return (
              <div key={f.name}>
                <div className="flex justify-between text-[11px] mb-0.5">
                  <span className="text-soc-text">{f.label || f.name}</span>
                  <span className={up ? "text-soc-red" : "text-soc-green"}>
                    {up ? "▲ increases" : "▼ decreases"}
                  </span>
                </div>
                <div className="h-2 rounded bg-soc-panel2 overflow-hidden">
                  <div
                    className={`h-full ${up ? "bg-soc-red/70" : "bg-soc-green/70"}`}
                    style={{ width: `${width}%` }}
                  />
                </div>
              </div>
            );
          })}
          <p className="text-[10px] text-soc-muted pt-1">
            Attributions are model-internal explanations, not proof of intent.
          </p>
        </div>
      )}
    </Panel>
  );
}

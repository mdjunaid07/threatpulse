import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import Panel from "./Panel";

export default function RiskTimeline({ snapshot }) {
  const trained = snapshot?.model_status === "TRAINED";
  const timeline = snapshot?.future_risk_timeline || [];

  const data = timeline.map((p) => ({
    label: p.offset_seconds === 0 ? "Now" : `+${p.offset_seconds}s`,
    risk: Math.round((p.risk ?? 0) * 100),
    risk_label: p.risk_label,
  }));

  return (
    <Panel
      title="Future Attack Risk"
      subtitle="Autoregressive K-step forecast from the World Model"
      right={
        <span className="text-[10px] text-soc-muted">
          horizon {timeline.length ? `${timeline.length - 1} steps` : "—"}
        </span>
      }
      className="h-full"
    >
      {!trained ? (
        <Empty text="Model not trained — no forecast. Run: python -m ml.training.train_lstm" />
      ) : data.length === 0 ? (
        <Empty text="Warming up state history…" />
      ) : (
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
              <defs>
                <linearGradient id="riskFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22D3EE" stopOpacity={0.55} />
                  <stop offset="100%" stopColor="#22D3EE" stopOpacity={0.03} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E2833" vertical={false} />
              <XAxis dataKey="label" stroke="#6B7A8D" fontSize={11} tickLine={false} />
              <YAxis
                domain={[0, 100]}
                stroke="#6B7A8D"
                fontSize={11}
                tickLine={false}
                unit="%"
              />
              <ReferenceLine y={50} stroke="#F59E0B" strokeDasharray="4 4" opacity={0.5} />
              <ReferenceLine y={75} stroke="#EF4444" strokeDasharray="4 4" opacity={0.5} />
              <Tooltip
                contentStyle={{
                  background: "#11161D",
                  border: "1px solid #1E2833",
                  borderRadius: 8,
                  fontSize: 12,
                  color: "#D7E0EA",
                }}
                formatter={(v, _n, p) => [`${v}%  (${p.payload.risk_label})`, "Forecast risk"]}
              />
              <Area
                type="monotone"
                dataKey="risk"
                stroke="#22D3EE"
                strokeWidth={2}
                fill="url(#riskFill)"
                isAnimationActive={false}
                dot={{ r: 3, fill: "#22D3EE" }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}

function Empty({ text }) {
  return (
    <div className="h-56 flex items-center justify-center text-center">
      <p className="text-xs text-soc-muted max-w-xs">{text}</p>
    </div>
  );
}

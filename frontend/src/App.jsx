import { useLiveFeed } from "./hooks/useLiveFeed";
import TopBar from "./components/TopBar";
import SummaryCards from "./components/SummaryCards";
import RiskTimeline from "./components/RiskTimeline";
import AttackProgression from "./components/AttackProgression";
import Explanation from "./components/Explanation";
import EventsTable from "./components/EventsTable";
import ForecastPanel from "./components/ForecastPanel";
import SensorHealth from "./components/SensorHealth";

export default function App() {
  const { snapshot, status } = useLiveFeed();

  return (
    <div className="min-h-screen bg-soc-bg text-soc-text p-3 sm:p-4">
      <div className="max-w-[1400px] mx-auto space-y-3">
        <TopBar snapshot={snapshot} status={status} />

        {status !== "connected" && (
          <div className="rounded-xl border border-soc-red/40 bg-soc-red/10 px-4 py-2 text-xs text-soc-red">
            Not connected to the backend WebSocket. Showing last known data (if
            any). The dashboard will reconnect automatically — check that the
            backend is running and reachable.
          </div>
        )}

        <SummaryCards snapshot={snapshot} />

        {/* Row 1: risk timeline (wide) + attack progression */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          <div className="lg:col-span-2">
            <RiskTimeline snapshot={snapshot} />
          </div>
          <AttackProgression snapshot={snapshot} />
        </div>

        {/* Row 2: explanation + forecast + sensor health */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          <Explanation snapshot={snapshot} />
          <ForecastPanel snapshot={snapshot} />
          <SensorHealth snapshot={snapshot} wsStatus={status} />
        </div>

        {/* Row 3: live events (full width) */}
        <EventsTable snapshot={snapshot} />

        <footer className="text-center text-[10px] text-soc-muted pt-2 pb-4">
          ThreatPulse · AI-Based Network Attack Forecasting · Team NeuroVex ·
          Smart India Hackathon 2026 — For use only inside an authorized,
          isolated lab. Forecasts are model predictions, not guarantees.
        </footer>
      </div>
    </div>
  );
}

import { HostSnapshot } from "../../architecture/hostView";

type SignalCardProps = {
  snapshot: HostSnapshot;
};

export function SignalCard({ snapshot }: SignalCardProps) {
  const signal = snapshot.signal;
  const isConnected = snapshot.project1.connected;

  const getActionBadgeClass = (action: string | null) => {
    if (!action) return "badge-action idle";
    switch (action.toUpperCase()) {
      case "BUY":
        return "badge-action buy";
      case "SELL":
        return "badge-action sell";
      case "HOLD":
        return "badge-action hold";
      default:
        return "badge-action idle";
    }
  };

  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3>Project 1 Signal Feed</h3>
          <p className="hint">Validated signals emitted via Project1IntegrationPort.</p>
        </div>
        <span className={`status ${isConnected ? "ready" : "disconnected"}`}>
          {isConnected ? "Connected" : "Project 1 Disconnected"}
        </span>
      </div>

      <div className="card-body">
        {!isConnected ? (
          <div className="signal-disconnected-box">
            <div className="signal-header-row">
              <span className={getActionBadgeClass("NO SIGNAL")}>
                NO SIGNAL
              </span>
              <span className="timestamp-tag">Timestamp: Unavailable</span>
            </div>
            <p className="hint" style={{ marginTop: 12 }}>
              {signal.message}
            </p>

            <div className="grid cols-4" style={{ marginTop: 16 }}>
              {["BUY", "SELL", "HOLD", "NO SIGNAL"].map((action) => (
                <div key={action} className="flow-step">
                  <span>Action State</span>
                  <strong style={{ fontSize: 13 }}>{action}</strong>
                  <p className="hint">
                    Inactive until Project 1 evaluates strategy conditions.
                  </p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="signal-active-box">
            <div className="signal-header-row">
              <span className={getActionBadgeClass(signal.action)}>
                {signal.action ?? "NO SIGNAL"}
              </span>
              <span className="timestamp-tag">{signal.timestamp ?? "N/A"}</span>
            </div>

            <div className="levels" style={{ marginTop: 16 }}>
              <div className="level">
                <span>Entry Level</span>
                <b>{snapshot.risk.entry ?? "Unavailable"}</b>
              </div>
              <div className="level">
                <span>Stop Loss</span>
                <b className="text-red">{snapshot.risk.stopLoss ?? "Unavailable"}</b>
              </div>
              <div className="level">
                <span>Target TP1</span>
                <b className="text-green">{snapshot.risk.takeProfits[0] ?? "Unavailable"}</b>
              </div>
              <div className="level">
                <span>Target TP2</span>
                <b className="text-green">{snapshot.risk.takeProfits[1] ?? "Unavailable"}</b>
              </div>
              <div className="level">
                <span>Target TP3</span>
                <b className="text-green">{snapshot.risk.takeProfits[2] ?? "Unavailable"}</b>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

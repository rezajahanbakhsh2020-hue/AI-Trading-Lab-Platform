import { HostSnapshot } from "../../architecture/hostView";
import { useI18n } from "../../i18n";

type SignalCardProps = {
  snapshot: HostSnapshot;
  onSync?: () => void;
};

export function SignalCard({ snapshot, onSync }: SignalCardProps) {
  const signal = snapshot.signal;
  const isConnected = snapshot.project1.connected;
  const { t, formatPercent, formatDate } = useI18n();

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

  const formatActionText = (action: string | null) => {
    if (!action) return t("signal.noSignal");
    switch (action.toUpperCase()) {
      case "BUY":
        return t("signal.buy");
      case "SELL":
        return t("signal.sell");
      case "HOLD":
        return t("signal.hold");
      default:
        return t("signal.noSignal");
    }
  };

  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3>{t("signal.feedTitle")}</h3>
          <p className="hint">{t("signal.feedSub")}</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {onSync && (
            <button
              className="btn btn-secondary"
              onClick={onSync}
              style={{ fontSize: 12, padding: "4px 10px" }}
              title={t("buttons.syncPort")}
            >
              {t("buttons.syncPort")}
            </button>
          )}
          <span className={`status ${isConnected ? "ready" : "disconnected"}`}>
            {isConnected ? t("status.connected") : t("topbar.project1Disconnected")}
          </span>
        </div>
      </div>

      <div className="card-body">
        {!isConnected ? (
          <div className="signal-disconnected-box">
            <div className="signal-header-row">
              <span className={getActionBadgeClass("NO SIGNAL")}>
                {t("signal.noSignal")}
              </span>
              <span className="timestamp-tag">{t("signal.timestamp")}: {t("status.unavailable")}</span>
            </div>
            <p className="hint" style={{ marginTop: 12 }}>
              {signal.message}
            </p>

            <div className="grid cols-4" style={{ marginTop: 16 }}>
              {["BUY", "SELL", "HOLD", "NO SIGNAL"].map((action) => (
                <div key={action} className="flow-step">
                  <span>{t("signal.actionState")}</span>
                  <strong style={{ fontSize: 13 }}>
                    {action === "BUY"
                      ? t("signal.buy")
                      : action === "SELL"
                      ? t("signal.sell")
                      : action === "HOLD"
                      ? t("signal.hold")
                      : t("signal.noSignal")}
                  </strong>
                  <p className="hint">{t("signal.inactiveMessage")}</p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="signal-active-box">
            <div className="signal-header-row">
              <span className={getActionBadgeClass(signal.action)}>
                {formatActionText(signal.action)}
              </span>
              <span className="timestamp-tag">
                {signal.timestamp ? `${t("signal.timestamp")}: ${formatDate(signal.timestamp)}` : "N/A"}
              </span>
            </div>

            <div className="grid cols-2" style={{ marginTop: 14 }}>
              <div className="flow-step">
                <span>{t("signal.strategyIdentity")}</span>
                <strong>{signal.strategyName ?? "Project 1 Strategy"}</strong>
                <p className="hint">{t("signal.timeframe")}: {signal.timeframe ?? "1h"}</p>
              </div>
              <div className="flow-step">
                <span>{t("signal.confidenceScore")}</span>
                <strong>
                  {signal.confidence != null
                    ? formatPercent(signal.confidence * 100)
                    : t("status.unavailable")}
                </strong>
                <p className="hint">{t("signal.signalId")}: {signal.signalId ?? "N/A"}</p>
              </div>
            </div>

            <div className="levels" style={{ marginTop: 16 }}>
              <div className="level">
                <span>{t("risk.entryLevel")}</span>
                <b>{snapshot.risk.entry ?? t("status.unavailable")}</b>
              </div>
              <div className="level">
                <span>{t("risk.stopLoss")}</span>
                <b className="text-red">{snapshot.risk.stopLoss ?? t("status.unavailable")}</b>
              </div>
              <div className="level">
                <span>{t("risk.targetTp1")}</span>
                <b className="text-green">{snapshot.risk.takeProfits[0] ?? t("status.unavailable")}</b>
              </div>
              <div className="level">
                <span>{t("risk.targetTp2")}</span>
                <b className="text-green">{snapshot.risk.takeProfits[1] ?? t("status.unavailable")}</b>
              </div>
              <div className="level">
                <span>{t("risk.targetTp3")}</span>
                <b className="text-green">{snapshot.risk.takeProfits[2] ?? t("status.unavailable")}</b>
              </div>
            </div>

            <div className="hint" style={{ marginTop: 12, fontSize: 11 }}>
              {t("signal.adapter")}: {snapshot.project1.adapterName} | {t("signal.port")}: {snapshot.project1.port}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

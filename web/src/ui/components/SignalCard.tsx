import { HostSnapshot } from "../../architecture/hostView";
import { useI18n } from "../../i18n";

type SignalCardProps = {
  snapshot: HostSnapshot;
  onSync?: () => void;
  onStageOrderIntent?: () => void;
  onSelectTimeframe?: (tf: string) => void;
};

export function SignalCard({
  snapshot,
  onSync,
  onStageOrderIntent,
  onSelectTimeframe,
}: SignalCardProps) {
  const signal = snapshot.signal;
  const isConnected = snapshot.project1.connected;
  const { t, formatPercent, formatDate } = useI18n();

  const supportedTimeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"];
  const currentTf = (signal.timeframe || snapshot.market.timeframe || "1h").toLowerCase();
  const currentSymbol = signal.symbol || snapshot.market.symbol || "XAUUSD";

  const getActionBadgeClass = (action: string | null, status?: string) => {
    if (!action) return "badge-action idle";
    const act = action.toUpperCase();
    if (act === "BUY") return "badge-action buy";
    if (act === "SELL") return "badge-action sell";
    if (act === "HOLD") return "badge-action hold";
    if (act === "NO TRADE" || act === "NO_TRADE" || status === "no-trade") return "badge-action idle";
    return "badge-action idle";
  };

  const formatActionText = (action: string | null, status?: string) => {
    if (!action) return t("signal.noCurrentSignal");
    const act = action.toUpperCase();
    if (act === "BUY") return t("signal.buy");
    if (act === "SELL") return t("signal.sell");
    if (act === "HOLD") return t("signal.hold");
    if (act === "NO TRADE" || act === "NO_TRADE" || status === "no-trade") return t("signal.noTrade");
    if (act === "NO CURRENT SIGNAL" || act === "NO SIGNAL" || status === "no-signal") return t("signal.noCurrentSignal");
    return action;
  };

  const isNoTrade = signal.status === "no-trade" || signal.action?.toUpperCase() === "NO TRADE" || signal.action?.toUpperCase() === "NO_TRADE";
  const isNoSignal = signal.status === "no-signal" || (!isNoTrade && (signal.action?.toUpperCase() === "NO SIGNAL" || signal.action?.toUpperCase() === "NO CURRENT SIGNAL" || !signal.timestamp));

  const mtfData = (signal.metadata?.mtf as any) || null;

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
        {/* Timeframe Selector Bar */}
        {onSelectTimeframe && (
          <div style={{ marginBottom: 14, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
            <span className="hint" style={{ fontSize: 11, fontWeight: 600 }}>
              {currentSymbol} · {t("signal.timeframe")}:
            </span>
            <div className="segmented-control" role="group" aria-label="Signal timeframe selector">
              {supportedTimeframes.map((tf) => (
                <button
                  key={tf}
                  type="button"
                  className={currentTf === tf ? "seg-btn active" : "seg-btn"}
                  onClick={() => onSelectTimeframe(tf)}
                  style={{ padding: "3px 8px", minHeight: 32, fontSize: 11 }}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>
        )}

        {!isConnected ? (
          <div className="signal-disconnected-box">
            <div className="signal-header-row">
              <span className={getActionBadgeClass("NO CURRENT SIGNAL")}>
                {t("signal.noCurrentSignal")}
              </span>
              <span className="timestamp-tag">{t("signal.timestamp")}: {t("status.unavailable")}</span>
            </div>
            <p className="hint" style={{ marginTop: 12 }}>
              {signal.message}
            </p>

            <div className="grid cols-4" style={{ marginTop: 16 }}>
              {["BUY", "SELL", "HOLD", "NO TRADE"].map((action) => (
                <div key={action} className="flow-step">
                  <span>{t("signal.actionState")}</span>
                  <strong style={{ fontSize: 13 }}>
                    {action === "BUY"
                      ? t("signal.buy")
                      : action === "SELL"
                      ? t("signal.sell")
                      : action === "HOLD"
                      ? t("signal.hold")
                      : t("signal.noTrade")}
                  </strong>
                  <p className="hint">{t("signal.inactiveMessage")}</p>
                </div>
              ))}
            </div>
          </div>
        ) : isNoTrade ? (
          <div className="signal-active-box">
            <div className="signal-header-row">
              <span className={getActionBadgeClass(signal.action, signal.status)}>
                {formatActionText(signal.action, signal.status)}
              </span>
              <span className="timestamp-tag">
                {signal.timestamp ? `${t("signal.timestamp")}: ${formatDate(signal.timestamp)}` : "N/A"}
              </span>
            </div>

            <div className="grid cols-2" style={{ marginTop: 14 }}>
              <div className="flow-step">
                <span>{t("signal.strategyIdentity")}</span>
                <strong>{signal.strategyName ?? "Project 1 Strategy"}</strong>
                <p className="hint">{t("signal.timeframe")}: {signal.timeframe ?? currentTf}</p>
              </div>
              <div className="flow-step">
                <span>{t("signal.actionState")}</span>
                <strong style={{ color: "var(--gold)" }}>{t("signal.noTrade")}</strong>
                <p className="hint">{t("signal.signalId")}: {signal.signalId ?? "N/A"}</p>
              </div>
            </div>

            <div className="notice-box warn-notice" style={{ marginTop: 14 }}>
              <p style={{ margin: 0, fontSize: 12, lineHeight: 1.5 }}>
                {signal.message || t("signal.evalNoTradeMsg", { symbol: currentSymbol, timeframe: signal.timeframe || currentTf })}
              </p>
            </div>

            {/* Authoritative P1 MTF Context */}
            {mtfData && (
              <div className="mtf-container" style={{ marginTop: 14, padding: 12, borderRadius: 8, background: "var(--bg-2)", border: "1px solid var(--line)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: "var(--gold)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                      {t("signal.mtfTitle")}
                    </span>
                    {mtfData.star_representation && (
                      <span style={{ fontSize: 13, letterSpacing: 2 }} title="Authoritative P1 Star Representation">
                        {mtfData.star_representation}
                      </span>
                    )}
                  </div>
                  {mtfData.classification && (
                    <span className="badge-soft" style={{ fontWeight: 600, color: mtfData.classification === "ALIGNED" ? "var(--green)" : "var(--amber)" }}>
                      {mtfData.classification}
                    </span>
                  )}
                </div>

                <div style={{ display: "flex", flexWrap: "wrap", gap: 12, fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
                  {mtfData.alignment_coverage != null && (
                    <span>
                      {t("signal.alignmentCoverage")}: <strong style={{ color: "var(--text)" }}>{mtfData.alignment_coverage} / 6</strong>
                    </span>
                  )}
                  <span>
                    {t("signal.selectedTimeframe")}: <strong style={{ color: "var(--text)" }}>{signal.timeframe ?? currentTf}</strong>
                  </span>
                </div>

                {Array.isArray(mtfData.signals) && mtfData.signals.length > 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                    {mtfData.signals.map((sig: any, idx: number) => (
                      <span key={`${sig.timeframe}-${idx}`} className="chip" style={{ fontSize: 11, padding: "2px 8px" }}>
                        <strong>{sig.timeframe}</strong>: {String(sig.direction || "").toUpperCase()}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div style={{ marginTop: 14, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span className="hint" style={{ fontSize: 11 }}>
                {t("signal.adapter")}: {snapshot.project1.adapterName} | {t("signal.port")}: {snapshot.project1.port}
              </span>
            </div>
          </div>
        ) : isNoSignal ? (
          <div className="signal-active-box">
            <div className="signal-header-row">
              <span className={getActionBadgeClass(signal.action, signal.status)}>
                {formatActionText(signal.action, signal.status)}
              </span>
              <span className="timestamp-tag">
                {t("signal.timeframe")}: {signal.timeframe || currentTf}
              </span>
            </div>

            <p className="hint" style={{ marginTop: 12, fontSize: 13, lineHeight: 1.5 }}>
              {signal.message || t("signal.evalNoSignalMsg", { symbol: currentSymbol, timeframe: currentTf })}
            </p>

            {/* Authoritative P1 MTF Context if available */}
            {mtfData && (
              <div className="mtf-container" style={{ marginTop: 14, padding: 12, borderRadius: 8, background: "var(--bg-2)", border: "1px solid var(--line)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: "var(--gold)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                      {t("signal.mtfTitle")}
                    </span>
                    {mtfData.star_representation && (
                      <span style={{ fontSize: 13, letterSpacing: 2 }} title="Authoritative P1 Star Representation">
                        {mtfData.star_representation}
                      </span>
                    )}
                  </div>
                  {mtfData.classification && (
                    <span className="badge-soft" style={{ fontWeight: 600, color: mtfData.classification === "ALIGNED" ? "var(--green)" : "var(--amber)" }}>
                      {mtfData.classification}
                    </span>
                  )}
                </div>

                <div style={{ display: "flex", flexWrap: "wrap", gap: 12, fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
                  {mtfData.alignment_coverage != null && (
                    <span>
                      {t("signal.alignmentCoverage")}: <strong style={{ color: "var(--text)" }}>{mtfData.alignment_coverage} / 6</strong>
                    </span>
                  )}
                  <span>
                    {t("signal.selectedTimeframe")}: <strong style={{ color: "var(--text)" }}>{signal.timeframe ?? currentTf}</strong>
                  </span>
                </div>

                {Array.isArray(mtfData.signals) && mtfData.signals.length > 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                    {mtfData.signals.map((sig: any, idx: number) => (
                      <span key={`${sig.timeframe}-${idx}`} className="chip" style={{ fontSize: 11, padding: "2px 8px" }}>
                        <strong>{sig.timeframe}</strong>: {String(sig.direction || "").toUpperCase()}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div style={{ marginTop: 14, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span className="hint" style={{ fontSize: 11 }}>
                {t("signal.adapter")}: {snapshot.project1.adapterName} | {t("signal.port")}: {snapshot.project1.port}
              </span>
            </div>
          </div>
        ) : (
          <div className="signal-active-box">
            <div className="signal-header-row">
              <span className={getActionBadgeClass(signal.action, signal.status)}>
                {formatActionText(signal.action, signal.status)}
              </span>
              <span className="timestamp-tag">
                {signal.timestamp ? `${t("signal.timestamp")}: ${formatDate(signal.timestamp)}` : "N/A"}
              </span>
            </div>

            <div className="grid cols-2" style={{ marginTop: 14 }}>
              <div className="flow-step">
                <span>{t("signal.strategyIdentity")}</span>
                <strong>{signal.strategyName ?? "Project 1 Strategy"}</strong>
                <p className="hint">{t("signal.timeframe")}: {signal.timeframe ?? currentTf}</p>
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

            {/* Authoritative P1 MTF Context */}
            {mtfData && (
              <div className="mtf-container" style={{ marginTop: 14, padding: 12, borderRadius: 8, background: "var(--bg-2)", border: "1px solid var(--line)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: "var(--gold)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                      {t("signal.mtfTitle")}
                    </span>
                    {mtfData.star_representation && (
                      <span style={{ fontSize: 13, letterSpacing: 2 }} title="Authoritative P1 Star Representation">
                        {mtfData.star_representation}
                      </span>
                    )}
                  </div>
                  {mtfData.classification && (
                    <span className="badge-soft" style={{ fontWeight: 600, color: mtfData.classification === "ALIGNED" ? "var(--green)" : "var(--amber)" }}>
                      {mtfData.classification}
                    </span>
                  )}
                </div>

                <div style={{ display: "flex", flexWrap: "wrap", gap: 12, fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
                  {mtfData.alignment_coverage != null && (
                    <span>
                      {t("signal.alignmentCoverage")}: <strong style={{ color: "var(--text)" }}>{mtfData.alignment_coverage} / 6</strong>
                    </span>
                  )}
                  <span>
                    {t("signal.selectedTimeframe")}: <strong style={{ color: "var(--text)" }}>{signal.timeframe ?? currentTf}</strong>
                  </span>
                </div>

                {Array.isArray(mtfData.signals) && mtfData.signals.length > 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                    {mtfData.signals.map((sig: any, idx: number) => (
                      <span key={`${sig.timeframe}-${idx}`} className="chip" style={{ fontSize: 11, padding: "2px 8px" }}>
                        <strong>{sig.timeframe}</strong>: {String(sig.direction || "").toUpperCase()}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div style={{ marginTop: 16, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span className="hint" style={{ fontSize: 11 }}>
                {t("signal.adapter")}: {snapshot.project1.adapterName} | {t("signal.port")}: {snapshot.project1.port}
              </span>
              {onStageOrderIntent && (
                <button
                  className="btn btn-primary"
                  onClick={onStageOrderIntent}
                  style={{ fontSize: 13, padding: "8px 14px", display: "flex", alignItems: "center", gap: 6 }}
                >
                  📋 {t("signal.stageOrderIntentAction")}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

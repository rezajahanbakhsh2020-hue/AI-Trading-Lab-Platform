import { useState } from "react";
import type { HostSnapshot } from "../../architecture/hostView";
import {
  extractBacktestState,
  SAMPLE_BACKTEST_DATA,
} from "../../architecture/backtest";
import { EmptyState } from "./EmptyState";
import { useI18n } from "../../i18n";

type BacktestViewerProps = {
  snapshot: HostSnapshot;
};

export function BacktestViewer({ snapshot }: BacktestViewerProps) {
  const { t, formatCurrency, formatPercent } = useI18n();
  const [useSample, setUseSample] = useState(false);

  const realState = extractBacktestState(snapshot);
  const backtestData = useSample ? SAMPLE_BACKTEST_DATA : realState.data;
  const status = useSample ? "available" : realState.status;

  const isAdmin = snapshot.security?.isAdmin ?? false;

  return (
    <div className="backtest-viewer space-y-6">
      <div className="card">
        <div className="card-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h3>{t("nav.backtest")}</h3>
            <p className="hint">{t("backtest.kicker") || "Walk-Forward & Deterministic Assessment Surface"}</p>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <button
              className={`btn ${useSample ? "btn-secondary" : "btn-primary"}`}
              onClick={() => setUseSample((prev) => !prev)}
              style={{ fontSize: 12, padding: "4px 10px" }}
            >
              {useSample ? t("backtest.useRealData") || "View Live State" : t("backtest.useSampleData") || "Preview Sample Backtest"}
            </button>
            <span className={`status ${status === "available" ? "ready" : status}`}>
              {status.toUpperCase()}
            </span>
          </div>
        </div>

        <div className="card-body">
          {status === "disconnected" && !useSample && (
            <EmptyState
              title={t("empty.noBacktestTitle") || "Project 1 Disconnected"}
              message={realState.message}
            />
          )}

          {status === "empty" && !useSample && (
            <EmptyState
              title={t("empty.noBacktestTitle") || "Empty Backtest Result"}
              message={realState.message}
            />
          )}

          {status === "unauthorized" && !useSample && (
            <EmptyState
              title="Access Denied"
              message={realState.message}
            />
          )}

          {(status === "invalid" || status === "failed" || status === "error") && !useSample && (
            <EmptyState
              title="Backtest Execution Failed"
              message={realState.message}
            />
          )}

          {status === "unavailable" && !useSample && (
            <EmptyState
              title={t("empty.noBacktestTitle") || "No Active Backtest Assessment"}
              message={realState.message}
            />
          )}

          {backtestData && (
            <div className="space-y-6">
              <div className="grid cols-4" style={{ gap: 12 }}>
                <div className="metric-box card" style={{ padding: 14 }}>
                  <span className="hint">{t("backtest.totalTrades") || "Total Trades"}</span>
                  <div className="metric" style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>
                    {backtestData.totalTrades}
                  </div>
                </div>

                <div className="metric-box card" style={{ padding: 14 }}>
                  <span className="hint">{t("backtest.winRate") || "Win Rate"}</span>
                  <div className="metric text-green" style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>
                    {formatPercent(backtestData.winRate)}
                  </div>
                </div>

                <div className="metric-box card" style={{ padding: 14 }}>
                  <span className="hint">{t("backtest.profitFactor") || "Profit Factor"}</span>
                  <div className="metric" style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>
                    {backtestData.profitFactor.toFixed(2)}
                  </div>
                </div>

                <div className="metric-box card" style={{ padding: 14 }}>
                  <span className="hint">{t("backtest.maxDrawdown") || "Max Drawdown"}</span>
                  <div className="metric text-red" style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>
                    {formatPercent(backtestData.maxDrawdown)}
                  </div>
                </div>
              </div>

              <div className="grid cols-2" style={{ gap: 16 }}>
                <div className="card" style={{ padding: 16 }}>
                  <h4>{t("backtest.summaryTitle") || "Performance Summary"}</h4>
                  <table className="table" style={{ marginTop: 12 }}>
                    <tbody>
                      <tr>
                        <th>{t("backtest.strategy") || "Strategy"}</th>
                        <td><strong>{backtestData.strategyName}</strong></td>
                      </tr>
                      <tr>
                        <th>{t("backtest.symbol") || "Symbol / Timeframe"}</th>
                        <td>{backtestData.symbol} ({backtestData.timeframe})</td>
                      </tr>
                      <tr>
                        <th>{t("backtest.netProfit") || "Net Profit"}</th>
                        <td className={backtestData.netProfit >= 0 ? "text-green" : "text-red"}>
                          <strong>{formatCurrency(backtestData.netProfit)}</strong>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div className="card" style={{ padding: 16 }}>
                  <h4>{t("backtest.stabilityTitle") || "Stability & Risk Assessment"}</h4>
                  {backtestData.stability ? (
                    <div style={{ marginTop: 12 }} className="space-y-3">
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span>{t("backtest.stabilityScore") || "Stability Score"}:</span>
                        <b style={{ fontSize: 18 }}>{(backtestData.stability.score * 100).toFixed(0)}%</b>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span>{t("backtest.riskLevel") || "Risk Level"}:</span>
                        <span className={`chip ${backtestData.stability.riskLevel === "low" ? "ready-chip" : "warn-chip"}`}>
                          {backtestData.stability.riskLevel.toUpperCase()}
                        </span>
                      </div>
                      <p className="hint" style={{ fontSize: 12, marginTop: 8 }}>
                        {backtestData.detail || "Walk-forward stability assessment evaluated directly against platform risk rules."}
                      </p>
                    </div>
                  ) : (
                    <p className="hint" style={{ marginTop: 12 }}>
                      {t("backtest.noStability") || "Stability metrics restricted or unavailable."}
                    </p>
                  )}
                </div>
              </div>

              <div className="card" style={{ padding: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <h4>{t("backtest.securityGateTitle") || "Security & Secret Boundary"}</h4>
                  <span className={`status ${isAdmin ? "ready" : "enforced"}`}>
                    {isAdmin ? "Admin Role" : "User Role"}
                  </span>
                </div>
                <p className="hint" style={{ marginTop: 8 }}>
                  {isAdmin
                    ? "Full backtest calibration parameters and detailed walk-forward matrices unlocked."
                    : "Proprietary indicator inputs, backtest seed logic, and internal trading parameters are sanitized by SecurityBoundaryService."}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

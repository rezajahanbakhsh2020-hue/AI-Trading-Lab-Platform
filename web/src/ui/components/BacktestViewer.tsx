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
            <p className="hint">{t("backtest.kicker")}</p>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <button
              className={`btn ${useSample ? "btn-secondary" : "btn-primary"}`}
              onClick={() => setUseSample((prev) => !prev)}
              style={{ fontSize: 12, padding: "4px 10px" }}
            >
              {useSample ? t("backtest.useRealData") : t("backtest.useSampleData")}
            </button>
            <span className={`status ${status === "available" ? "ready" : status}`}>
              {status.toUpperCase()}
            </span>
          </div>
        </div>

        <div className="card-body">
          {status === "disconnected" && !useSample && (
            <EmptyState
              title={t("empty.noBacktestTitle")}
              message={realState.message}
            />
          )}

          {status === "empty" && !useSample && (
            <EmptyState
              title={t("empty.noBacktestTitle")}
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
              title={t("empty.noBacktestTitle")}
              message={realState.message}
            />
          )}

          {backtestData && (
            <div className="space-y-6">
              <div className="grid cols-4" style={{ gap: 12 }}>
                <div className="metric-box card" style={{ padding: 14 }}>
                  <span className="hint">{t("backtest.totalTrades")}</span>
                  <div className="metric" style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>
                    {backtestData.totalTrades}
                  </div>
                </div>

                <div className="metric-box card" style={{ padding: 14 }}>
                  <span className="hint">{t("backtest.winRate")}</span>
                  <div className="metric text-green" style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>
                    {formatPercent(backtestData.winRate)}
                  </div>
                </div>

                <div className="metric-box card" style={{ padding: 14 }}>
                  <span className="hint">{t("backtest.profitFactor")}</span>
                  <div className="metric" style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>
                    {backtestData.profitFactor.toFixed(2)}
                  </div>
                </div>

                <div className="metric-box card" style={{ padding: 14 }}>
                  <span className="hint">{t("backtest.maxDrawdown")}</span>
                  <div className="metric text-red" style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>
                    {formatPercent(backtestData.maxDrawdown)}
                  </div>
                </div>
              </div>

              <div className="grid cols-2" style={{ gap: 16 }}>
                <div className="card" style={{ padding: 16 }}>
                  <h4>{t("backtest.summaryTitle")}</h4>
                  <div className="table-responsive" style={{ marginTop: 12 }}>
                    <table className="table">
                      <tbody>
                        <tr>
                          <th>{t("backtest.strategy")}</th>
                          <td><strong>{backtestData.strategyName}</strong></td>
                        </tr>
                        <tr>
                          <th>{t("backtest.symbol")}</th>
                          <td>{backtestData.symbol} ({backtestData.timeframe})</td>
                        </tr>
                        <tr>
                          <th>{t("backtest.netProfit")}</th>
                          <td className={backtestData.netProfit >= 0 ? "text-green" : "text-red"}>
                            <strong>{formatCurrency(backtestData.netProfit)}</strong>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="card" style={{ padding: 16 }}>
                  <h4>{t("backtest.stabilityTitle")}</h4>
                  {backtestData.stability ? (
                    <div style={{ marginTop: 12 }} className="space-y-3">
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span>{t("backtest.stabilityScore")}:</span>
                        <b style={{ fontSize: 18 }}>{(backtestData.stability.score * 100).toFixed(0)}%</b>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span>{t("backtest.riskLevel")}:</span>
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
                      {t("backtest.noStability")}
                    </p>
                  )}
                </div>
              </div>

              {backtestData.walkForward && (
                <div className="card space-y-4" style={{ padding: 16 }}>
                  <div>
                    <h4>{t("walkForward.title")}</h4>
                    <p className="hint" style={{ fontSize: 13, marginTop: 2 }}>
                      {t("walkForward.sub")}
                    </p>
                  </div>

                  <div className="grid cols-4" style={{ gap: 12 }}>
                    <div className="metric-box card" style={{ padding: 12 }}>
                      <span className="hint">{t("walkForward.overallOosWinRate")}</span>
                      <div className="metric text-green" style={{ fontSize: 18, fontWeight: 700, marginTop: 2 }}>
                        {formatPercent(backtestData.walkForward.overallOutOfSampleWinRate)}
                      </div>
                    </div>
                    <div className="metric-box card" style={{ padding: 12 }}>
                      <span className="hint">{t("walkForward.overallOosPF")}</span>
                      <div className="metric" style={{ fontSize: 18, fontWeight: 700, marginTop: 2 }}>
                        {backtestData.walkForward.overallOutOfSampleProfitFactor.toFixed(2)}
                      </div>
                    </div>
                    <div className="metric-box card" style={{ padding: 12 }}>
                      <span className="hint">{t("walkForward.overallOosMaxDrawdown")}</span>
                      <div className="metric text-red" style={{ fontSize: 18, fontWeight: 700, marginTop: 2 }}>
                        {formatPercent(backtestData.walkForward.overallOutOfSampleMaxDrawdown)}
                      </div>
                    </div>
                    <div className="metric-box card" style={{ padding: 12 }}>
                      <span className="hint">{t("walkForward.overallOosNetProfit")}</span>
                      <div className="metric text-green" style={{ fontSize: 18, fontWeight: 700, marginTop: 2 }}>
                        {formatCurrency(backtestData.walkForward.overallOutOfSampleNetProfit)}
                      </div>
                    </div>
                  </div>

                  {backtestData.walkForward.windows.length > 0 && (
                    <div className="table-responsive">
                      <table className="table" style={{ fontSize: 13 }}>
                        <thead>
                          <tr>
                            <th>#</th>
                            <th>{t("walkForward.inSampleWinRate")}</th>
                            <th>{t("walkForward.inSamplePF")}</th>
                            <th>{t("walkForward.outOfSampleWinRate")}</th>
                            <th>{t("walkForward.outOfSamplePF")}</th>
                            <th>{t("walkForward.outOfSampleDrawdown")}</th>
                            <th>{t("walkForward.outOfSampleProfit")}</th>
                            <th>{t("walkForward.efficiencyRatio")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {backtestData.walkForward.windows.map((w) => (
                            <tr key={w.windowIndex}>
                              <td><strong>Window {w.windowIndex}</strong></td>
                              <td>{formatPercent(w.inSampleWinRate)} ({w.inSampleTrades})</td>
                              <td>{w.inSampleProfitFactor.toFixed(2)}</td>
                              <td className="text-green">{formatPercent(w.outOfSampleWinRate)} ({w.outOfSampleTrades})</td>
                              <td>{w.outOfSampleProfitFactor.toFixed(2)}</td>
                              <td className="text-red">{formatPercent(w.outOfSampleMaxDrawdown)}</td>
                              <td className={w.outOfSampleNetProfit >= 0 ? "text-green" : "text-red"}>
                                {formatCurrency(w.outOfSampleNetProfit)}
                              </td>
                              <td>
                                <span className={`chip ${w.efficiencyRatio >= 0.85 ? "ready-chip" : "warn-chip"}`}>
                                  {w.efficiencyRatio.toFixed(2)}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              <div className="card" style={{ padding: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <h4>{t("backtest.securityGateTitle")}</h4>
                  <span className={`status ${isAdmin ? "ready" : "enforced"}`}>
                    {isAdmin ? "Admin Role" : "User Role"}
                  </span>
                </div>
                <p className="hint" style={{ marginTop: 8 }}>
                  {isAdmin
                    ? t("backtest.adminSecurityMsg")
                    : t("backtest.userSecurityMsg")}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

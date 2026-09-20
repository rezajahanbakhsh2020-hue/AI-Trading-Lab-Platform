import type { HostSnapshot } from "../../architecture/hostView";
import { extractPerformanceAnalytics } from "../../architecture/performance";
import { EmptyState } from "./EmptyState";
import { useI18n } from "../../i18n";

export function PerformanceViewer({ snapshot }: { snapshot: HostSnapshot }) {
  const { t, formatPercent, formatCurrency } = useI18n();
  const perfState = extractPerformanceAnalytics(snapshot);

  if (
    perfState.status === "disconnected" ||
    perfState.status === "unavailable" ||
    perfState.status === "unauthorized" ||
    perfState.status === "empty" ||
    perfState.status === "failed" ||
    !perfState.summary
  ) {
    return (
      <div className="performance-view space-y-6" data-testid="performance-viewer">
        <section className="card">
          <div className="card-head flex-header-row">
            <h3>📈 {t("nav.performance")}</h3>
            <span className={`status ${perfState.status === "unauthorized" ? "unavailable" : "warn"}`}>
              {perfState.status.toUpperCase()}
            </span>
          </div>
          <div className="card-body">
            <EmptyState
              title={t("empty.noPerfTitle")}
              message={perfState.message}
            />
          </div>
        </section>
      </div>
    );
  }

  const s = perfState.summary;
  const dd = s.drawdown_profile;
  const r = s.risk_profile;

  return (
    <div className="performance-view space-y-6" data-testid="performance-viewer">
      {/* Top Headline Cards */}
      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-head">
            <h3>{t("backtest.totalTrades")}</h3>
            <span className="chip ready-chip">{s.strategy_name}</span>
          </div>
          <div className="card-body">
            <div className="metric">{s.total_trades}</div>
            <p className="hint">{s.symbol} ({s.timeframe})</p>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h3>{t("backtest.winRate")}</h3>
            <span className={`status ${s.win_rate >= 0.5 ? "ready" : "warn"}`}>
              {formatPercent(s.win_rate)}
            </span>
          </div>
          <div className="card-body">
            <div className="metric text-green">{formatPercent(s.win_rate)}</div>
            <p className="hint">Win / Loss Ratio: {r ? r.win_loss_ratio : "N/A"}</p>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h3>{t("backtest.profitFactor")}</h3>
            <span className={`status ${s.profit_factor >= 1.5 ? "ready" : s.profit_factor >= 1.0 ? "warn" : "unavailable"}`}>
              {s.profit_factor.toFixed(2)}
            </span>
          </div>
          <div className="card-body">
            <div className="metric">{s.profit_factor.toFixed(2)}</div>
            <p className="hint">Reward to Risk Expectancy</p>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h3>{t("backtest.maxDrawdown")}</h3>
            <span className={`status ${s.max_drawdown <= 0.15 ? "ready" : s.max_drawdown <= 0.25 ? "warn" : "unavailable"}`}>
              {formatPercent(s.max_drawdown)}
            </span>
          </div>
          <div className="card-body">
            <div className="metric text-red">{formatPercent(s.max_drawdown)}</div>
            <p className="hint">Classification: {dd ? dd.risk_classification : "N/A"}</p>
          </div>
        </div>
      </div>

      {/* Main Analytics Breakdown */}
      <div className="grid cols-2" style={{ marginBottom: 16 }}>
        {/* Drawdown & Recovery Profile Card */}
        <section className="card">
          <div className="card-head flex-header-row">
            <h3>📉 Drawdown & Recovery Profile</h3>
            <span className={`chip ${dd?.risk_classification === "LOW" ? "ready-chip" : "warn-chip"}`}>
              {dd?.risk_classification || "MEDIUM"} RISK
            </span>
          </div>
          <div className="card-body">
            <table className="table">
              <tbody>
                <tr>
                  <th>Max Peak-to-Trough Drawdown</th>
                  <td className="text-red">
                    <strong>{formatPercent(s.max_drawdown)}</strong>
                  </td>
                </tr>
                <tr>
                  <th>Recovery Factor Ratio</th>
                  <td>
                    <strong>{dd?.recovery_factor != null ? dd.recovery_factor.toFixed(2) : "N/A"}</strong>
                  </td>
                </tr>
                <tr>
                  <th>Estimated Sharpe Ratio</th>
                  <td className="text-green">
                    <strong>{s.sharpe_ratio_estimate != null ? s.sharpe_ratio_estimate.toFixed(2) : "N/A"}</strong>
                  </td>
                </tr>
                <tr>
                  <th>Cumulative Net Profit</th>
                  <td className="text-green">
                    <strong>{formatCurrency(s.net_profit)}</strong>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* Walk-Forward & Out-of-Sample Performance */}
        <section className="card">
          <div className="card-head flex-header-row">
            <h3>🔄 Walk-Forward Efficiency & Stability</h3>
            <span className="chip ready-chip">Out-of-Sample Validation</span>
          </div>
          <div className="card-body">
            <table className="table">
              <tbody>
                <tr>
                  <th>Walk-Forward Efficiency Ratio</th>
                  <td>
                    <strong>{s.walk_forward_efficiency != null ? formatPercent(s.walk_forward_efficiency) : "N/A"}</strong>
                  </td>
                </tr>
                <tr>
                  <th>Out-of-Sample Consistency</th>
                  <td>
                    <strong>{s.walk_forward_consistency != null ? formatPercent(s.walk_forward_consistency) : "N/A"}</strong>
                  </td>
                </tr>
                <tr>
                  <th>Evaluation Detail</th>
                  <td style={{ fontSize: 13 }}>{s.detail || "Authentic backtest assessment executed."}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}

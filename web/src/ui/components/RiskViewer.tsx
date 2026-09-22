import type { HostSnapshot } from "../../architecture/hostView";
import { extractPerformanceAnalytics } from "../../architecture/performance";
import { useI18n } from "../../i18n";

export function RiskViewer({ snapshot }: { snapshot: HostSnapshot }) {
  const { t, formatCurrency, formatPercent } = useI18n();
  const perfState = extractPerformanceAnalytics(snapshot);

  const risk = snapshot.risk;
  const summary = perfState.summary;
  const r = summary?.risk_profile;

  const levels = [
    [t("risk.entryLevel"), risk.entry],
    [t("risk.stopLoss"), risk.stopLoss],
    [t("risk.targetTp1"), risk.takeProfits[0] ?? null],
    [t("risk.targetTp2"), risk.takeProfits[1] ?? null],
    [t("risk.targetTp3"), risk.takeProfits[2] ?? null],
  ] as const;

  return (
    <div className="risk-view space-y-6" data-testid="risk-viewer">
      {/* Risk Compliance Gate Summary Header */}
      <div className="grid cols-3" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-head">
            <h3>Risk Assessment Status</h3>
            <span className={`status ${r?.risk_assessment_status === "compliant" ? "ready" : r?.risk_assessment_status === "degraded" ? "warn" : "unavailable"}`}>
              {(r?.risk_assessment_status || "evaluating").toUpperCase()}
            </span>
          </div>
          <div className="card-body">
            <div className="metric">
              {r?.risk_assessment_status === "compliant" ? "COMPLIANT" : r?.risk_assessment_status || "PENDING"}
            </div>
            <p className="hint">Risk Level Classification: <strong>{(r?.risk_level || "medium").toUpperCase()}</strong></p>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h3>Position Risk Pass</h3>
            <span className={`chip ${r?.position_risk_pass ? "ready-chip" : "warn-chip"}`}>
              {r?.position_risk_pass ? "PASSED" : "FAILED"}
            </span>
          </div>
          <div className="card-body">
            <div className="metric">{r?.reward_to_risk_expectancy != null ? `${r.reward_to_risk_expectancy.toFixed(2)}:1` : "N/A"}</div>
            <p className="hint">Reward to Risk Expectancy</p>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h3>Drawdown Limit Pass</h3>
            <span className={`chip ${r?.drawdown_limit_pass ? "ready-chip" : "warn-chip"}`}>
              {r?.drawdown_limit_pass ? "PASSED" : "BREACHED"}
            </span>
          </div>
          <div className="card-body">
            <div className="metric text-red">{r?.max_drawdown != null ? formatPercent(r.max_drawdown) : "N/A"}</div>
            <p className="hint">Observed Max Drawdown</p>
          </div>
        </div>
      </div>

      <div className="grid cols-2" style={{ marginBottom: 16 }}>
        {/* Trade Setup Geometry Levels */}
        <section className="card">
          <div className="card-head flex-header-row">
            <h3>🎯 {t("risk.tradeRiskBreakdown")}</h3>
            <span className={`status ${risk.status === "available" ? "ready" : "unavailable"}`}>
              {risk.status === "available" ? t("status.activeSetup") : t("status.unavailable")}
            </span>
          </div>
          <div className="card-body">
            <div className="levels">
              {levels.map(([label, value]) => (
                <div className="level" key={label} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
                  <span>{label}</span>
                  <b className={label.includes("Stop") || label.includes("ضرر") || label.includes("خسارة") || label.includes("Durdur") ? "text-red" : label.includes("Take") || label.includes("تارگت") || label.includes("هدف") || label.includes("Hedef") ? "text-green" : ""}>
                    {value == null ? t("status.unavailable") : formatCurrency(value)}
                  </b>
                </div>
              ))}
            </div>
            <p className="hint" style={{ marginTop: 12 }}>
              {risk.message}
            </p>
          </div>
        </section>

        {/* Risk / Reward Compliance Calculator */}
        <section className="card">
          <div className="card-head flex-header-row">
            <h3>⚖️ {t("risk.riskRewardCalculator")}</h3>
            <span className="status ready">{t("risk.ratio")}</span>
          </div>
          <div className="card-body">
            <p className="hint" style={{ marginBottom: 12 }}>
              {t("risk.riskDesc")}
            </p>
            <div className="table-responsive">
              <table className="table">
                <tbody>
                  <tr>
                    <th>{t("risk.accountRiskLimit")}</th>
                    <td><strong>{t("risk.perTrade")}</strong></td>
                  </tr>
                  <tr>
                    <th>Min Target Ratio Expectancy</th>
                    <td><strong>{r?.reward_to_risk_expectancy != null ? `${r.reward_to_risk_expectancy.toFixed(2)}:1` : t("risk.ratio")}</strong></td>
                  </tr>
                  <tr>
                    <th>Win / Loss Ratio</th>
                    <td><strong>{r?.win_loss_ratio != null ? r.win_loss_ratio.toFixed(2) : "N/A"}</strong></td>
                  </tr>
                  <tr>
                    <th>Drawdown Classification</th>
                    <td><span className="chip ready-chip">{(r?.risk_level || "low").toUpperCase()}</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

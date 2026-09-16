import type { HostSnapshot } from "../../architecture/hostView";
import { extractAutonomousAuthorization } from "../../architecture/authorization";
import { useI18n } from "../../i18n";

type AutonomousAuthorizationViewerProps = {
  snapshot: HostSnapshot;
};

export function AutonomousAuthorizationViewer({
  snapshot,
}: AutonomousAuthorizationViewerProps) {
  const { t, formatDate } = useI18n();
  const auth = extractAutonomousAuthorization(snapshot);

  const getStatusBadgeClass = (status: string) => {
    switch (status.toUpperCase()) {
      case "AUTHORIZED":
        return "status ready";
      case "UNAUTHORIZED":
      case "REJECTED":
        return "status disconnected";
      case "NO_SIGNAL":
        return "status warn";
      case "DISCONNECTED":
      default:
        return "status unavailable";
    }
  };

  const getStatusText = (status: string) => {
    switch (status.toUpperCase()) {
      case "AUTHORIZED":
        return t("authorization.authorized");
      case "UNAUTHORIZED":
      case "REJECTED":
        return t("authorization.unauthorized");
      case "NO_SIGNAL":
        return t("authorization.noSignal");
      case "DISCONNECTED":
        return t("authorization.disconnected");
      default:
        return status;
    }
  };

  return (
    <div className="authorization-viewer space-y-6">
      <div className="grid cols-2">
        {/* Authorization Overview Card */}
        <section className="card">
          <div className="card-head">
            <h3>{t("authorization.statusTitle")}</h3>
            <span className={getStatusBadgeClass(auth.status)}>
              {getStatusText(auth.status)}
            </span>
          </div>
          <div className="card-body">
            <div className="metric muted" style={{ fontSize: 18, fontWeight: "bold", marginBottom: 8 }}>
              {auth.isAuthorized ? "AUTHORIZED" : "NOT AUTHORIZED"}
            </div>
            <p className="hint">{auth.reason}</p>
            {auth.timestamp && (
              <p className="hint" style={{ marginTop: 10, fontSize: 11 }}>
                {t("authorization.timestampLabel")}: {formatDate(auth.timestamp * 1000)}
              </p>
            )}
          </div>
        </section>

        {/* Risk / Reward Gate Card */}
        <section className="card">
          <div className="card-head">
            <h3>{t("authorization.riskRewardTitle")}</h3>
            <span className={`status ${auth.riskRewardRatio != null && auth.riskRewardRatio >= 1.0 ? "ready" : "unavailable"}`}>
              {auth.riskRewardRatio != null ? `${auth.riskRewardRatio.toFixed(2)} : 1` : "N/A"}
            </span>
          </div>
          <div className="card-body">
            <p className="hint">
              Evaluates trade geometry risk-to-reward ratio against required threshold (minimum 1.0:1) before autonomous dispatch.
            </p>
            <div className="calc-preview-box" style={{ marginTop: 12 }}>
              <div className="calc-row">
                <span>Required R:R Ratio:</span>
                <b>&ge; 1.0 : 1</b>
              </div>
              <div className="calc-row">
                <span>Calculated Setup R:R:</span>
                <b>{auth.riskRewardRatio != null ? `${auth.riskRewardRatio.toFixed(2)} : 1` : "N/A"}</b>
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* Execution Gate Breakdown */}
      <section className="card">
        <div className="card-head">
          <h3>{t("authorization.gateChecksTitle")}</h3>
          <span className="chip">{auth.checks.length} Gate Checks</span>
        </div>
        <div className="card-body">
          {auth.checks.length === 0 ? (
            <p className="hint">No gate checks available for evaluation.</p>
          ) : (
            <div className="table-responsive">
              <table className="table">
                <thead>
                  <tr>
                    <th>Gate Check</th>
                    <th>Status</th>
                    <th>Evaluation Detail / Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {auth.checks.map((check) => (
                    <tr key={check.id}>
                      <td>
                        <strong>{check.label}</strong>
                      </td>
                      <td>
                        <span className={`status ${check.passed ? "ready" : "disconnected"}`}>
                          {check.passed ? t("authorization.passed") : t("authorization.failed")}
                        </span>
                      </td>
                      <td>{check.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

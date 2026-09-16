import {
  extractAuthorizationFromSnapshot,
  getAuthorizationStatusBadge,
  summarizeAuthorizationChecks,
} from "../../architecture/authorization";
import type { HostSnapshot } from "../../architecture/hostView";
import { useI18n } from "../../i18n";

interface AutonomousAuthorizationViewerProps {
  snapshot: HostSnapshot;
}

export function AutonomousAuthorizationViewer({
  snapshot,
}: AutonomousAuthorizationViewerProps) {
  const { t } = useI18n();
  const auth = extractAuthorizationFromSnapshot(snapshot);
  const { badgeClass, labelKey } = getAuthorizationStatusBadge(auth.status);
  const summary = summarizeAuthorizationChecks(auth.checks);
  const isAdmin = snapshot.security?.isAdmin ?? false;

  return (
    <div className="authorization-viewer space-y-6">
      {/* Overview Verdict Card */}
      <section className="card">
        <div className="card-head">
          <div>
            <p className="kicker">{t("authorization.verdictKicker") || "Assurance Gate Verdict"}</p>
            <h3>{t("authorization.verdictTitle") || "Autonomous Execution Authorization"}</h3>
          </div>
          <span className={`chip ${badgeClass}`}>
            <span
              className={`dot ${
                auth.status === "AUTHORIZED"
                  ? "ready"
                  : auth.status === "REJECTED"
                  ? "warn"
                  : "off"
              }`}
            />
            <strong>{t(labelKey) || auth.status}</strong>
          </span>
        </div>
        <div className="card-body">
          <div
            style={{
              background: "var(--bg-2)",
              border: "1px solid var(--line)",
              borderRadius: "var(--radius)",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              gap: 12,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
              <div>
                <span className="hint">{t("authorization.reasonLabel") || "Evaluation Reason:"}</span>
                <p style={{ margin: "4px 0 0", fontSize: 14, fontWeight: 600 }}>
                  {auth.reason}
                </p>
              </div>
              {auth.riskRewardRatio != null && (
                <div style={{ textAlign: "right" }}>
                  <span className="hint">{t("authorization.rrLabel") || "R:R Ratio:"}</span>
                  <div className="metric" style={{ margin: 0, color: "var(--gold)" }}>
                    1 : {auth.riskRewardRatio.toFixed(2)}
                  </div>
                </div>
              )}
            </div>

            <div
              style={{
                display: "flex",
                gap: 12,
                flexWrap: "wrap",
                alignItems: "center",
                fontSize: 12,
                color: "var(--text-muted)",
                borderTop: "1px solid var(--line)",
                paddingTop: 10,
              }}
            >
              <span>
                {t("authorization.passedGates") || "Passed Gates:"}{" "}
                <strong style={{ color: "var(--green)" }}>
                  {summary.passedCount} / {summary.total} ({summary.passPercentage}%)
                </strong>
              </span>
              <span>•</span>
              <span>
                {t("authorization.symbolTimeframe") || "Symbol & TF:"}{" "}
                <strong>
                  {snapshot.market.symbol} ({snapshot.market.timeframe})
                </strong>
              </span>
              {auth.timestamp != null && (
                <>
                  <span>•</span>
                  <span>
                    {t("authorization.evaluatedAt") || "Evaluated:"}{" "}
                    {new Date(auth.timestamp * 1000).toUTCString()}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Assurance Gate Checks Breakdown */}
      <section className="card">
        <div className="card-head">
          <h3>{t("authorization.gatesTitle") || "Deterministic Execution Gate Breakdown"}</h3>
          <span className="chip">
            {t("authorization.gatesCount", { count: summary.passedCount, total: summary.total })}
          </span>
        </div>
        <div className="card-body">
          <div className="grid cols-2" style={{ gap: 12 }}>
            {auth.checks.map((check) => (
              <div
                key={check.id}
                style={{
                  background: "var(--bg-2)",
                  border: `1px solid ${
                    check.passed ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)"
                  }`,
                  borderRadius: "8px",
                  padding: "14px",
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ fontSize: 13 }}>{check.label}</strong>
                  <span className={`status ${check.passed ? "ready" : "disconnected"}`}>
                    {check.passed
                      ? t("authorization.gatePassed") || "PASSED"
                      : t("authorization.gateFailed") || "REJECTED"}
                  </span>
                </div>
                <p className="hint" style={{ margin: 0, fontSize: 12, color: check.passed ? "var(--text)" : "var(--text-muted)" }}>
                  {check.reason}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Security Boundary & Authorization Guardrails Notice */}
      <section className="card">
        <div className="card-head">
          <h3>{t("authorization.securityTitle") || "Autonomous Boundary & Role Assurance"}</h3>
          <span className={`status ${isAdmin ? "ready" : "enforced"}`}>
            {isAdmin ? "Admin Role" : "User Role"}
          </span>
        </div>
        <div className="card-body">
          <p className="hint">
            {isAdmin
              ? t("authorization.adminNotice") ||
                "Admin account authenticated. Full autonomous gate breakdown and parameter geometry reasons are unredacted."
              : t("authorization.userNotice") ||
                "Standard user role active. Security Boundary Service redacts proprietary level geometry reasons for unauthorized roles to prevent indicator reverse engineering."}
          </p>
        </div>
      </section>
    </div>
  );
}

import { useI18n } from "../../i18n";

export interface OperationalErrorDetails {
  whatHappenedKey: string;
  whyLikelyKey: string;
  whatToCancelKey: string;
  whatIfContinuesKey: string;
  correlationId?: string;
  rawDetails?: string;
}

interface OperationalErrorBannerProps {
  error: OperationalErrorDetails;
  onDismiss?: () => void;
  onRetry?: () => void;
}

export function OperationalErrorBanner({
  error,
  onDismiss,
  onRetry,
}: OperationalErrorBannerProps) {
  const { t } = useI18n();

  return (
    <div
      style={{
        padding: "1rem 1.25rem",
        borderRadius: "8px",
        backgroundColor: "rgba(239, 68, 68, 0.12)",
        border: "1px solid #ef4444",
        color: "#f8fafc",
        marginBottom: "1.25rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.75rem",
      }}
      role="alert"
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontWeight: 700, fontSize: "1rem", color: "#fca5a5" }}>
          <span>⚠️</span>
          <span>{t(error.whatHappenedKey as any) || error.whatHappenedKey}</span>
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="btn btn-ghost"
            style={{ padding: "0.25rem 0.5rem", minHeight: "36px", color: "#94a3b8" }}
            aria-label="Dismiss"
          >
            ✕
          </button>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.75rem", fontSize: "0.875rem" }}>
        <div>
          <div style={{ color: "#94a3b8", fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 600 }}>
            {t("errors.whyTitle")}
          </div>
          <div style={{ color: "#e2e8f0", marginTop: "0.125rem" }}>
            {t(error.whyLikelyKey as any) || error.whyLikelyKey}
          </div>
        </div>

        <div>
          <div style={{ color: "#94a3b8", fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 600 }}>
            {t("errors.actionTitle")}
          </div>
          <div style={{ color: "#e2e8f0", marginTop: "0.125rem" }}>
            {t(error.whatToCancelKey as any) || error.whatToCancelKey}
          </div>
        </div>

        <div>
          <div style={{ color: "#94a3b8", fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 600 }}>
            {t("errors.supportTitle")}
          </div>
          <div style={{ color: "#e2e8f0", marginTop: "0.125rem" }}>
            {t(error.whatIfContinuesKey as any) || error.whatIfContinuesKey}
          </div>
        </div>
      </div>

      {error.correlationId && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: "0.5rem", borderTop: "1px solid rgba(239, 68, 68, 0.2)", fontSize: "0.75rem", color: "#fca5a5" }}>
          <span>Reference Correlation ID: <code>{error.correlationId}</code></span>
          {onRetry && (
            <button
              onClick={onRetry}
              className="btn btn-secondary"
              style={{ minHeight: "36px", padding: "0.25rem 0.75rem", fontSize: "0.75rem" }}
            >
              🔄 {t("buttons.refresh")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

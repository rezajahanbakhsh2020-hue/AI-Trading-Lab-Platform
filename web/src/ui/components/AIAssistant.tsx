import { useState } from "react";
import type { HostSnapshot } from "../../architecture/hostView";
import {
  processAIGatewayRequest,
  type AICapability,
  type AIResponsePayload,
  type AIProviderStatus,
  type AISimulatedErrorType,
} from "../../architecture/aiGateway";
import { useI18n } from "../../i18n";

interface AIAssistantProps {
  snapshot: HostSnapshot;
}

export function AIAssistant({ snapshot }: AIAssistantProps) {
  const { t } = useI18n();

  const [capability, setCapability] = useState<AICapability>("explain_signal");
  const [selectedSymbol, setSelectedSymbol] = useState(snapshot.market.symbol || "XAUUSD");
  const [promptQuery, setPromptQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [aiResponse, setAiResponse] = useState<AIResponsePayload | null>(null);

  // Provider configuration toggle for testing real vs unavailable vs error states
  const [simulatedProviderStatus, setSimulatedProviderStatus] =
    useState<AIProviderStatus>("unavailable");
  const [simulatedErrorType, setSimulatedErrorType] =
    useState<AISimulatedErrorType>("none");

  const handleProcessRequest = () => {
    setIsLoading(true);
    setAiResponse(null);

    const resp = processAIGatewayRequest(
      snapshot,
      {
        requestId: `req_${Math.random().toString(36).substring(2, 9)}`,
        userId: snapshot.security?.userId || "guest_user",
        capability,
        targetSymbol: selectedSymbol,
        promptQuery: promptQuery.trim() || undefined,
      },
      {
        status: simulatedProviderStatus,
        name:
          simulatedProviderStatus === "available"
            ? "HttpAIProviderAdapter"
            : simulatedProviderStatus === "error"
            ? "HttpAIProviderAdapter"
            : "UnavailableAIProviderAdapter",
        responseText:
          simulatedProviderStatus === "available"
            ? `AI Explanation for ${capability.toUpperCase()} (${selectedSymbol}): Market conditions and signal alignment verified within permitted platform boundaries. No strategy logic exposed.`
            : "AI unavailable / provider not configured",
        simulatedErrorType,
      }
    );

    setAiResponse(resp);
    setIsLoading(false);
  };

  const capabilities: { id: AICapability; labelKey: string }[] = [
    { id: "explain_signal", labelKey: "ai.capabilities.explain_signal" },
    { id: "summarize_market", labelKey: "ai.capabilities.summarize_market" },
    { id: "summarize_timeline", labelKey: "ai.capabilities.summarize_timeline" },
    { id: "explain_health", labelKey: "ai.capabilities.explain_health" },
  ];

  const getStatusBadge = () => {
    if (isLoading) {
      return <span className="status loading">{t("status.loading")}</span>;
    }
    if (!aiResponse) {
      return (
        <span
          className={`status ${
            simulatedProviderStatus === "available"
              ? "ready"
              : simulatedProviderStatus === "error"
              ? "error"
              : "unavailable"
          }`}
        >
          {simulatedProviderStatus === "available"
            ? t("ai.status.available")
            : simulatedProviderStatus === "error"
            ? t("status.error")
            : t("ai.status.unavailable")}
        </span>
      );
    }
    if (aiResponse.status === "PERMISSION_DENIED") {
      return <span className="status error">{t("ai.status.permissionDenied")}</span>;
    }
    if (aiResponse.status === "UNAVAILABLE") {
      return <span className="status unavailable">{t("ai.status.unavailable")}</span>;
    }
    if (aiResponse.status === "SUCCESS") {
      return <span className="status ready">{t("status.ready")}</span>;
    }
    return <span className="status error">{t("status.error")}</span>;
  };

  return (
    <div className="ai-assistant-view space-y-6" data-testid="ai-assistant-component">
      <div className="grid cols-2">
        {/* Left Column: Capability & Request Configuration */}
        <div className="card">
          <div className="card-head">
            <h3>{t("ai.title")}</h3>
            {getStatusBadge()}
          </div>
          <div className="card-body">
            <p className="hint" style={{ marginBottom: 14 }}>
              {t("ai.subTitle")}
            </p>

            {/* Capability Selector */}
            <div style={{ marginBottom: 16 }}>
              <label className="label" style={{ fontWeight: 600, display: "block", marginBottom: 6 }}>
                Select AI Capability:
              </label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                {capabilities.map((cap) => (
                  <button
                    key={cap.id}
                    className={`btn ${capability === cap.id ? "btn-primary" : "btn-secondary"}`}
                    onClick={() => setCapability(cap.id)}
                    style={{ fontSize: 12, padding: "8px 10px", textAlign: "center" }}
                  >
                    {t(cap.labelKey)}
                  </button>
                ))}
              </div>
            </div>

            {/* Symbol & Timeframe Selection */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 16 }}>
              <div>
                <label className="label" style={{ fontWeight: 600, display: "block", marginBottom: 4 }}>
                  Target Market:
                </label>
                <select
                  aria-label="Target Market"
                  className="input"
                  value={selectedSymbol}
                  onChange={(e) => setSelectedSymbol(e.target.value)}
                  style={{ width: "100%", padding: "8px" }}
                >
                  {["XAUUSD", "EURUSD", "GBPUSD", "BTCUSD", "SPX500"].map((sym) => (
                    <option key={sym} value={sym}>
                      {sym}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="label" style={{ fontWeight: 600, display: "block", marginBottom: 4 }}>
                  Provider State:
                </label>
                <select
                  aria-label="Simulate Provider"
                  className="input"
                  value={simulatedProviderStatus}
                  onChange={(e) => {
                    const status = e.target.value as AIProviderStatus;
                    setSimulatedProviderStatus(status);
                    if (status === "error") {
                      setSimulatedErrorType("timeout");
                    } else {
                      setSimulatedErrorType("none");
                    }
                  }}
                  style={{ width: "100%", padding: "8px" }}
                >
                  <option value="unavailable">No Provider (Default)</option>
                  <option value="not_configured">Not Configured</option>
                  <option value="misconfigured">Misconfigured</option>
                  <option value="available">Connected Provider (HTTP Adapter)</option>
                  <option value="error">Provider Error / Timeout</option>
                </select>
              </div>
            </div>

            {/* Error Type Selector if Provider State is 'error' */}
            {simulatedProviderStatus === "error" && (
              <div style={{ marginBottom: 16 }}>
                <label className="label" style={{ fontWeight: 600, display: "block", marginBottom: 4 }}>
                  Simulated Error Condition:
                </label>
                <select
                  aria-label="Simulated Error Condition"
                  className="input"
                  value={simulatedErrorType}
                  onChange={(e) => setSimulatedErrorType(e.target.value as AISimulatedErrorType)}
                  style={{ width: "100%", padding: "8px" }}
                >
                  <option value="timeout">Request Timeout</option>
                  <option value="rate_limit">HTTP 429 Rate Limit Exceeded</option>
                  <option value="auth_error">HTTP 401 Authentication Failed</option>
                  <option value="provider_error">HTTP 500 Service Error</option>
                </select>
              </div>
            )}

            {/* Optional Prompt Query */}
            <div style={{ marginBottom: 16 }}>
              <label className="label" style={{ fontWeight: 600, display: "block", marginBottom: 4 }}>
                {t("ai.promptLabel")}
              </label>
              <input
                type="text"
                className="input"
                placeholder={t("ai.promptPlaceholder")}
                value={promptQuery}
                onChange={(e) => setPromptQuery(e.target.value)}
                style={{ width: "100%", padding: "8px 10px" }}
              />
            </div>

            {/* Submit Button */}
            <button
              className="btn btn-primary"
              onClick={handleProcessRequest}
              disabled={isLoading}
              style={{ width: "100%", padding: "10px", fontSize: 14 }}
            >
              {isLoading ? t("ai.buttons.processing") : t("ai.buttons.generate")}
            </button>
          </div>
        </div>

        {/* Right Column: Security & Allowed Context Boundary */}
        <div className="card">
          <div className="card-head">
            <h3>{t("ai.boundary.title")}</h3>
            <span className="chip ready-chip">{t("ai.boundary.sanitized")}</span>
          </div>
          <div className="card-body">
            <p className="hint" style={{ marginBottom: 12 }}>
              {t("ai.boundary.protectedNote")}
            </p>

            <div className="table-responsive">
              <table className="table">
                <tbody>
                  <tr>
                    <th>Identity / Role</th>
                    <td>
                      <strong>{(snapshot.security?.role || "user").toUpperCase()}</strong>
                    </td>
                  </tr>
                  <tr>
                    <th>Selected Capability</th>
                    <td>
                      <code>{capability}</code>
                    </td>
                  </tr>
                  <tr>
                    <th>Target Symbol</th>
                    <td>{selectedSymbol}</td>
                  </tr>
                  <tr>
                    <th>Signal Context Included</th>
                    <td>
                      {snapshot.signal?.action && snapshot.signal.action !== "NO SIGNAL" ? (
                        <span className="chip ready-chip">{snapshot.signal.action}</span>
                      ) : (
                        <span className="chip">None / Neutral</span>
                      )}
                    </td>
                  </tr>
                  <tr>
                    <th>Market Context Included</th>
                    <td>
                      {snapshot.market.quote ? (
                        <span className="chip ready-chip">Quote Active</span>
                      ) : (
                        <span className="chip">Disconnected</span>
                      )}
                    </td>
                  </tr>
                  <tr>
                    <th>Timeline Events Included</th>
                    <td>{snapshot.activity ? snapshot.activity.length : 0} events</td>
                  </tr>
                  <tr>
                    <th>Project 1 Code / Secrets</th>
                    <td>
                      <span className="chip" style={{ color: "var(--color-green, #10b981)" }}>
                        ✓ Strictly Filtered Out
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* Response Display Box */}
      {aiResponse && (
        <section className="card" style={{ marginTop: 16 }}>
          <div className="card-head">
            <h3>{t("ai.responseTitle")}</h3>
            <span className="chip" style={{ fontSize: 11 }}>
              Adapter: {aiResponse.providerName}
            </span>
          </div>
          <div className="card-body">
            {aiResponse.status === "UNAVAILABLE" ? (
              <div className="empty-state-box" style={{ padding: "20px", textAlign: "center" }}>
                <span className="status unavailable" style={{ display: "inline-block", marginBottom: 10 }}>
                  {t("ai.status.unavailable")}
                </span>
                <p style={{ fontWeight: 600, fontSize: 15, margin: "8px 0" }}>
                  AI unavailable / provider not configured
                </p>
                <p className="hint">{t("ai.unavailableMessage")}</p>
              </div>
            ) : aiResponse.status === "PERMISSION_DENIED" ? (
              <div className="empty-state-box" style={{ padding: "20px", textAlign: "center" }}>
                <span className="status error" style={{ display: "inline-block", marginBottom: 10 }}>
                  {t("ai.status.permissionDenied")}
                </span>
                <p style={{ fontWeight: 600, fontSize: 15, margin: "8px 0", color: "#ef4444" }}>
                  {aiResponse.content}
                </p>
                <p className="hint">{t("ai.permissionDeniedMessage")}</p>
              </div>
            ) : aiResponse.status === "ERROR" ? (
              <div className="empty-state-box" style={{ padding: "20px", textAlign: "center" }}>
                <span className="status error" style={{ display: "inline-block", marginBottom: 10 }}>
                  {t("status.error")}
                </span>
                <p style={{ fontWeight: 600, fontSize: 15, margin: "8px 0", color: "#ef4444" }}>
                  {aiResponse.content}
                </p>
                <p className="hint">
                  {aiResponse.errorMessage || "An error occurred with the AI provider."}
                </p>
              </div>
            ) : (
              <div>
                <div
                  style={{
                    background: "var(--color-bg-subtle, #18181b)",
                    padding: "16px",
                    borderRadius: "6px",
                    borderLeft: "4px solid var(--color-primary, #3b82f6)",
                    fontSize: 14,
                    lineHeight: 1.6,
                  }}
                >
                  {aiResponse.content}
                </div>

                {aiResponse.contextSummary && (
                  <div style={{ marginTop: 16, fontSize: 12, opacity: 0.8 }}>
                    <strong>Consumed Context Summary:</strong> ID: <code>{aiResponse.contextSummary.contextId}</code> | User: {aiResponse.contextSummary.userId} | Capability: {aiResponse.contextSummary.capability} | Sanitized: {aiResponse.contextSummary.isSanitized ? "Yes" : "No"}
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}

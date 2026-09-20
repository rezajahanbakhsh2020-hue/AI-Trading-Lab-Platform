import { useState } from "react";
import { Link } from "react-router-dom";
import type { HostSnapshot } from "../../architecture/hostView";
import {
  filterOrderIntentsByState,
  searchOrderIntentsBySymbol,
  transitionOrderIntentState,
  type OrderIntentPayload,
  type OrderLifecycleState,
} from "../../architecture/orderIntent";
import { useI18n } from "../../i18n";

interface OrderIntentViewerProps {
  snapshot: HostSnapshot;
  onTransitionIntent?: (
    intentId: string,
    targetState: OrderLifecycleState,
    reason?: string
  ) => void;
  onRequestExecution?: (intentId: string) => void;
}

export function OrderIntentViewer({
  snapshot,
  onTransitionIntent,
  onRequestExecution,
}: OrderIntentViewerProps) {
  const { t, formatCurrency } = useI18n();

  const [searchQuery, setSearchQuery] = useState("");
  const [stateFilter, setStateFilter] = useState<OrderLifecycleState | "ALL">("ALL");
  const [localIntents, setLocalIntents] = useState<OrderIntentPayload[]>(
    () => (snapshot.orderIntents ? [...snapshot.orderIntents] : [])
  );

  const initialIntents = snapshot.orderIntents ? [...snapshot.orderIntents] : [];
  const currentIntents = localIntents.length > 0 ? localIntents : initialIntents;

  const searched = searchOrderIntentsBySymbol(currentIntents, searchQuery);
  const filtered = filterOrderIntentsByState(searched, stateFilter);

  const handleAction = (
    intent: OrderIntentPayload,
    targetState: OrderLifecycleState
  ) => {
    let reasonPrompt = "";
    try {
      if (typeof window !== "undefined" && window.prompt) {
        if (targetState === "CANCELLED") {
          reasonPrompt = window.prompt(t("orderIntent.confirmCancelReason")) || "";
        } else if (targetState === "REJECTED") {
          reasonPrompt = window.prompt(t("orderIntent.confirmRejectReason")) || "";
        }
      }
    } catch {
      reasonPrompt = "";
    }

    try {
      const updated = transitionOrderIntentState(intent, targetState, reasonPrompt || undefined);
      setLocalIntents((prev) =>
        prev.map((i) => (i.order_intent_id === intent.order_intent_id ? updated : i))
      );
      if (onTransitionIntent) {
        onTransitionIntent(intent.order_intent_id, targetState, reasonPrompt || undefined);
      }
    } catch (e: any) {
      alert(e.message || "Failed to transition state");
    }
  };

  const getStateBadgeClass = (state: OrderLifecycleState) => {
    switch (state) {
      case "STAGED":
        return "chip ready-chip";
      case "CANCELLED":
        return "chip warn-chip";
      case "REJECTED":
        return "chip danger-chip";
      case "EXPIRED":
        return "chip muted-chip";
      default:
        return "chip";
    }
  };

  const execGw = snapshot.executionGateway;

  return (
    <div className="order-intent-viewer space-v-6">
      {/* Non-Execution Disclosure Banner & Gateway Status */}
      <section className="card execution-disclosure-card">
        <div className="card-body">
          <div className="disclosure-header">
            <span className="disclosure-icon" aria-hidden="true">ℹ️</span>
            <div>
              <h4 className="disclosure-title">
                {t("orderIntent.stagedOrderIntent")}
              </h4>
              <p className="disclosure-text">
                {t("orderIntent.disclosure")}
              </p>
            </div>
          </div>

          {/* Execution Gateway Capability Status */}
          <div className="gateway-status-bar">
            <div className="gateway-status-item">
              <span className="gateway-status-label">{t("orderIntent.executionBoundaryTitle")}:</span>
              <span className="gateway-status-badge">
                {execGw?.status || "unconfigured"}
              </span>
            </div>
            <div className="gateway-status-item">
              <span className="gateway-status-label">{t("orderIntent.allowsExecution")}:</span>
              <span className="gateway-status-value text-red">
                {execGw?.allows_execution ? "TRUE" : t("orderIntent.disabledExecution")}
              </span>
            </div>
          </div>

            {/* Workflow Navigation Action Bridges */}
            <div style={{ marginTop: 14, display: "flex", gap: 10, flexWrap: "wrap", borderTop: "1px solid var(--border-color, rgba(255,255,255,0.1))", paddingTop: 12 }}>
              <Link to="/risk" className="btn btn-secondary" style={{ fontSize: 12, padding: "6px 12px", textDecoration: "none" }}>
                📊 {t("orderIntent.navToRisk")}
              </Link>
              <Link to="/notifications" className="btn btn-secondary" style={{ fontSize: 12, padding: "6px 12px", textDecoration: "none" }}>
                🔔 {t("orderIntent.navToNotifications")}
              </Link>
              <Link to="/health" className="btn btn-secondary" style={{ fontSize: 12, padding: "6px 12px", textDecoration: "none" }}>
                🛡️ {t("orderIntent.navToHealth")}
              </Link>
            </div>
        </div>
      </section>

      {/* Control Bar: Search & Filter */}
      <section className="card">
        <div className="card-body control-bar">
          <div className="control-search">
            <input
              type="text"
              className="input-search"
              placeholder={t("orderIntent.searchPlaceholder")}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label={t("orderIntent.searchPlaceholder")}
            />
          </div>

          <div className="control-filter">
            <label className="filter-label" htmlFor="order-intent-state-filter">
              {t("orderIntent.filterState")}:
            </label>
            <select
              id="order-intent-state-filter"
              className="select-filter"
              value={stateFilter}
              onChange={(e) =>
                setStateFilter(e.target.value as OrderLifecycleState | "ALL")
              }
              aria-label={t("orderIntent.filterState")}
            >
              <option value="ALL">{t("orderIntent.filterAll")}</option>
              <option value="STAGED">{t("orderIntent.staged")}</option>
              <option value="CANCELLED">{t("orderIntent.cancelled")}</option>
              <option value="REJECTED">{t("orderIntent.rejected")}</option>
              <option value="EXPIRED">{t("orderIntent.expired")}</option>
            </select>
          </div>
        </div>
      </section>

      {/* Order Intent List / Cards */}
      {filtered.length === 0 ? (
        <section className="card empty-card-view">
          <div className="card-body empty-state">
            <div className="empty-icon-ring" aria-hidden="true">📋</div>
            <h4>{t("orderIntent.emptyTitle")}</h4>
            <p className="hint">{t("orderIntent.emptySub")}</p>
          </div>
        </section>
      ) : (
        <div className="grid cols-2 order-intent-grid">
          {filtered.map((intent) => {
            const isBuy = intent.direction === "buy";
            const createdDate = new Date(intent.creation_timestamp * 1000).toUTCString();

            return (
              <section key={intent.order_intent_id} className="card order-intent-card">
                <div className="card-head intent-card-header">
                  <div className="intent-title-group">
                    <span className={`badge-direction ${isBuy ? "buy" : "sell"}`}>
                      {intent.direction.toUpperCase()}
                    </span>
                    <strong className="intent-symbol">{intent.symbol}</strong>
                    <span className="hint">({intent.order_type.toUpperCase()})</span>
                  </div>
                  <span className={getStateBadgeClass(intent.lifecycle_state)}>
                    {t(`orderIntent.${intent.lifecycle_state.toLowerCase()}` as any) || intent.lifecycle_state}
                  </span>
                </div>

                <div className="card-body intent-card-body">
                  {/* Prices & Geometry */}
                  <div className="grid cols-2 level-grid">
                    <div>
                      <span className="hint">{t("orderIntent.requestedPrice")}</span>
                      <b className="mono-val">
                        {intent.requested_price != null
                          ? formatCurrency(intent.requested_price)
                          : t("status.unavailable")}
                      </b>
                    </div>
                    <div>
                      <span className="hint">{t("orderIntent.requestedQuantity")}</span>
                      <b className="mono-val">
                        {intent.requested_quantity != null
                          ? intent.requested_quantity
                          : t("status.unavailable")}
                      </b>
                    </div>
                    <div>
                      <span className="hint">{t("orderIntent.stopLoss")}</span>
                      <b className="mono-val text-red">
                        {intent.stop_loss != null
                          ? formatCurrency(intent.stop_loss)
                          : t("status.unavailable")}
                      </b>
                    </div>
                    <div>
                      <span className="hint">{t("orderIntent.takeProfits")}</span>
                      <b className="mono-val text-green">
                        {intent.take_profit_1 != null
                          ? formatCurrency(intent.take_profit_1)
                          : t("status.unavailable")}
                      </b>
                    </div>
                  </div>

                  {/* Metadata identifiers */}
                  <div className="intent-meta-section">
                    <div className="intent-meta-row">
                      <span>{t("orderIntent.intentId")}:</span>
                      <span className="mono-val">{intent.order_intent_id}</span>
                    </div>
                    <div className="intent-meta-row">
                      <span>{t("orderIntent.idempotencyKey")}:</span>
                      <span className="mono-val text-truncate">
                        {intent.idempotency_key}
                      </span>
                    </div>
                    <div className="intent-meta-row">
                      <span>{t("orderIntent.creationTime")}:</span>
                      <span>{createdDate}</span>
                    </div>
                    {intent.rejection_reason && (
                      <div className="text-red hint-reason">
                        <b>Reason:</b> {intent.rejection_reason}
                      </div>
                    )}
                  </div>

                  {/* Reconciliation Status Section */}
                  {intent.reconciliation && (
                    <div className="reconciliation-section">
                      <div className="reconciliation-header">
                        <span className="hint font-semibold">
                          {t("orderIntent.reconciliationTitle")}:
                        </span>
                        <span className="chip warn-chip">
                          {t(`orderIntent.${intent.reconciliation.status.toLowerCase()}Rec` as any) || intent.reconciliation.status}
                        </span>
                      </div>
                      <p className="hint">
                        {intent.reconciliation.reason}
                      </p>
                    </div>
                  )}

                  {/* Execution attempts history */}
                  {intent.execution_attempts && intent.execution_attempts.length > 0 && (
                    <div className="execution-attempts-section">
                      <span className="hint font-semibold">
                        {t("orderIntent.executionAttemptsTitle")}:
                      </span>
                      {intent.execution_attempts.map((att, idx) => (
                        <div key={idx} className="attempt-item-box">
                          <div className="attempt-item-header">
                            <span className="mono-val font-bold uppercase text-amber">
                              {att.status}
                            </span>
                            <span className="hint text-dim">
                              {new Date(att.timestamp * 1000).toLocaleTimeString()}
                            </span>
                          </div>
                          <p className="hint">{att.reason}</p>
                          <div className="mono-disclaimer text-red">
                            {t("orderIntent.externalExecutionDisclaimer")}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Actions for legal state transitions & gateway submission */}
                  {intent.is_staged && (
                    <div className="intent-actions-row">
                      <button
                        className="btn btn-primary btn-action-gateway"
                        onClick={() => onRequestExecution && onRequestExecution(intent.order_intent_id)}
                        aria-label={t("orderIntent.requestExecutionAction")}
                      >
                        ⚡ {t("orderIntent.requestExecutionAction")}
                      </button>
                      <div className="btn-action-group">
                        <button
                          className="btn btn-secondary btn-cancel"
                          onClick={() => handleAction(intent, "CANCELLED")}
                          aria-label={t("orderIntent.cancelAction")}
                        >
                          {t("orderIntent.cancelAction")}
                        </button>
                        <button
                          className="btn btn-secondary btn-reject"
                          onClick={() => handleAction(intent, "REJECTED")}
                          aria-label={t("orderIntent.rejectAction")}
                        >
                          {t("orderIntent.rejectAction")}
                        </button>
                        <button
                          className="btn btn-secondary btn-expire"
                          onClick={() => handleAction(intent, "EXPIRED")}
                          aria-label={t("orderIntent.expireAction")}
                        >
                          {t("orderIntent.expireAction")}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}

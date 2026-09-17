import { useState } from "react";
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
    () => snapshot.orderIntents ? [...snapshot.orderIntents] : []
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
    <div className="order-intent-viewer space-y-6">
      {/* Non-Execution Disclosure Banner & Gateway Status */}
      <section className="card bg-amber-950/20 border-amber-500/30">
        <div className="card-body p-4 space-y-3">
          <div className="flex items-start gap-3">
            <span className="text-amber-400 text-xl">ℹ️</span>
            <div>
              <h4 className="font-semibold text-amber-300 text-sm mb-1">
                {t("orderIntent.stagedOrderIntent")}
              </h4>
              <p className="text-xs text-amber-200/80 leading-relaxed">
                {t("orderIntent.disclosure")}
              </p>
            </div>
          </div>

          {/* Execution Gateway Capability Status */}
          <div className="border-t border-amber-500/20 pt-3 flex flex-wrap items-center justify-between gap-2 text-xs">
            <div className="flex items-center gap-2 text-amber-200">
              <span className="font-semibold">{t("orderIntent.executionBoundaryTitle")}:</span>
              <span className="font-mono uppercase bg-amber-900/40 px-2 py-0.5 rounded border border-amber-500/30">
                {execGw?.status || "unconfigured"}
              </span>
            </div>
            <div className="flex items-center gap-2 text-amber-300/80 text-[11px]">
              <span>{t("orderIntent.allowsExecution")}:</span>
              <span className="font-mono font-bold text-rose-400">
                {execGw?.allows_execution ? "TRUE" : t("orderIntent.disabledExecution")}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Control Bar: Search & Filter */}
      <section className="card">
        <div className="card-body p-4 flex flex-col md:flex-row gap-4 justify-between items-stretch md:items-center">
          <div className="flex-1 min-w-[240px]">
            <input
              type="text"
              className="input w-full"
              placeholder={t("orderIntent.searchPlaceholder")}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label={t("orderIntent.searchPlaceholder")}
            />
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs text-muted whitespace-nowrap">
              {t("orderIntent.filterState")}:
            </label>
            <select
              className="select text-sm"
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
        <section className="card text-center py-12">
          <div className="card-body">
            <p className="text-2xl mb-2">📋</p>
            <h3 className="text-lg font-semibold mb-1">
              {t("orderIntent.emptyTitle")}
            </h3>
            <p className="text-xs text-muted">{t("orderIntent.emptySub")}</p>
          </div>
        </section>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((intent) => {
            const isBuy = intent.direction === "buy";
            const createdDate = new Date(intent.creation_timestamp * 1000).toUTCString();

            return (
              <section key={intent.order_intent_id} className="card">
                <div className="card-head flex items-center justify-between border-b border-line p-4">
                  <div className="flex items-center gap-2">
                    <span
                      className={`font-bold text-sm px-2 py-0.5 rounded ${
                        isBuy
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                      }`}
                    >
                      {intent.direction.toUpperCase()}
                    </span>
                    <strong className="text-base font-semibold">{intent.symbol}</strong>
                    <span className="text-xs text-muted">({intent.order_type.toUpperCase()})</span>
                  </div>
                  <span className={getStateBadgeClass(intent.lifecycle_state)}>
                    {t(`orderIntent.${intent.lifecycle_state.toLowerCase()}` as any) || intent.lifecycle_state}
                  </span>
                </div>

                <div className="card-body p-4 space-y-3">
                  {/* Prices & Geometry */}
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-muted block">{t("orderIntent.requestedPrice")}</span>
                      <b className="font-mono">
                        {intent.requested_price != null
                          ? formatCurrency(intent.requested_price)
                          : t("status.unavailable")}
                      </b>
                    </div>
                    <div>
                      <span className="text-muted block">{t("orderIntent.requestedQuantity")}</span>
                      <b className="font-mono">
                        {intent.requested_quantity != null
                          ? intent.requested_quantity
                          : t("status.unavailable")}
                      </b>
                    </div>
                    <div>
                      <span className="text-muted block">{t("orderIntent.stopLoss")}</span>
                      <b className="font-mono text-rose-400">
                        {intent.stop_loss != null
                          ? formatCurrency(intent.stop_loss)
                          : t("status.unavailable")}
                      </b>
                    </div>
                    <div>
                      <span className="text-muted block">{t("orderIntent.takeProfits")}</span>
                      <b className="font-mono text-emerald-400">
                        {intent.take_profit_1 != null
                          ? formatCurrency(intent.take_profit_1)
                          : t("status.unavailable")}
                      </b>
                    </div>
                  </div>

                  {/* Metadata identifiers */}
                  <div className="border-t border-line/50 pt-2 space-y-1 text-[11px] text-muted">
                    <div className="flex justify-between">
                      <span>{t("orderIntent.intentId")}:</span>
                      <span className="font-mono text-foreground">{intent.order_intent_id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>{t("orderIntent.idempotencyKey")}:</span>
                      <span className="font-mono text-foreground truncate max-w-[180px]">
                        {intent.idempotency_key}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>{t("orderIntent.creationTime")}:</span>
                      <span>{createdDate}</span>
                    </div>
                    {intent.rejection_reason && (
                      <div className="text-rose-400 pt-1">
                        <b>Reason:</b> {intent.rejection_reason}
                      </div>
                    )}
                  </div>

                  {/* Reconciliation Status Section */}
                  {intent.reconciliation && (
                    <div className="border-t border-line/50 pt-2 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-semibold text-muted block">
                          {t("orderIntent.reconciliationTitle")}:
                        </span>
                        <span className="chip text-[10px] bg-amber-900/30 text-amber-300 border border-amber-500/30">
                          {t(`orderIntent.${intent.reconciliation.status.toLowerCase()}Rec` as any) || intent.reconciliation.status}
                        </span>
                      </div>
                      <p className="text-[10px] text-muted leading-tight">
                        {intent.reconciliation.reason}
                      </p>
                    </div>
                  )}

                  {/* Execution attempts history */}
                  {intent.execution_attempts && intent.execution_attempts.length > 0 && (
                    <div className="border-t border-line/50 pt-2 space-y-1">
                      <span className="text-[11px] font-semibold text-muted block">
                        {t("orderIntent.executionAttemptsTitle")}:
                      </span>
                      {intent.execution_attempts.map((att, idx) => (
                        <div
                          key={idx}
                          className="bg-black/20 p-2 rounded text-[11px] border border-line/30 space-y-0.5"
                        >
                          <div className="flex justify-between items-center">
                            <span className="font-mono font-bold uppercase text-amber-400">
                              {att.status}
                            </span>
                            <span className="text-[10px] text-muted">
                              {new Date(att.timestamp * 1000).toLocaleTimeString()}
                            </span>
                          </div>
                          <p className="text-muted text-[10px] leading-tight">{att.reason}</p>
                          <div className="text-[9px] text-rose-400/80 font-mono">
                            {t("orderIntent.externalExecutionDisclaimer")}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Actions for legal state transitions & gateway submission */}
                  {intent.is_staged && (
                    <div className="border-t border-line/50 pt-3 flex flex-wrap items-center justify-between gap-2">
                      <button
                        className="btn btn-primary text-xs px-3 py-1 bg-amber-600 hover:bg-amber-500 text-white"
                        onClick={() => onRequestExecution && onRequestExecution(intent.order_intent_id)}
                      >
                        ⚡ {t("orderIntent.requestExecutionAction")}
                      </button>
                      <div className="flex items-center gap-1.5">
                        <button
                          className="btn btn-secondary text-xs px-2 py-1 text-rose-400 border-rose-500/30 hover:bg-rose-500/10"
                          onClick={() => handleAction(intent, "CANCELLED")}
                        >
                          {t("orderIntent.cancelAction")}
                        </button>
                        <button
                          className="btn btn-secondary text-xs px-2 py-1 text-amber-400 border-amber-500/30 hover:bg-amber-500/10"
                          onClick={() => handleAction(intent, "REJECTED")}
                        >
                          {t("orderIntent.rejectAction")}
                        </button>
                        <button
                          className="btn btn-secondary text-xs px-2 py-1 text-muted hover:bg-white/5"
                          onClick={() => handleAction(intent, "EXPIRED")}
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

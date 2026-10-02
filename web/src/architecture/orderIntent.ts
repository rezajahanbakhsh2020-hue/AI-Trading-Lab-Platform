/**
 * Frontend domain contract and lifecycle types for Order Intent (Project 2 Foundation).
 * Represents an authorized staged order intent.
 * DOES NOT represent routed, filled, or broker-executed orders.
 */

export type OrderLifecycleState = "STAGED" | "REJECTED" | "CANCELLED" | "EXPIRED";

import type {
  ExecutionAttemptResultPayload,
  ExecutionReconciliationRecordPayload,
} from "./executionGateway";

export interface OrderIntentPayload {
  order_intent_id: string;
  authorization_id: string;
  user_id: string;
  symbol: string;
  direction: "buy" | "sell";
  order_type: "market" | "limit" | "stop";
  requested_price?: number | null;
  requested_quantity?: number | null;
  stop_loss?: number | null;
  take_profit_1?: number | null;
  take_profit_2?: number | null;
  take_profit_3?: number | null;
  time_in_force?: string | null;
  idempotency_key: string;
  creation_timestamp: number;
  lifecycle_state: OrderLifecycleState;
  is_staged: boolean;
  is_terminal: boolean;
  rejection_reason?: string | null;
  publication_id?: string | null;
  signal_id?: string | null;
  decision_id?: string | null;
  canonical_live_decision_fingerprint?: string | null;
  candidate_id?: string | null;
  research_evidence_id?: string | null;
  strategy_id?: string | null;
  research_fingerprint?: string | null;
  runtime_authorization_fingerprint?: string | null;
  strategy_version?: string | null;
  trailing_stop?: Record<string, any> | null;
  invalidation_condition?: string | null;
  execution_attempts?: ExecutionAttemptResultPayload[];
  reconciliation?: ExecutionReconciliationRecordPayload | null;
}

/**
 * Helper function to filter order intents by lifecycle state.
 */
export function filterOrderIntentsByState(
  intents: readonly OrderIntentPayload[],
  stateFilter: OrderLifecycleState | "ALL"
): OrderIntentPayload[] {
  if (stateFilter === "ALL") {
    return [...intents];
  }
  return intents.filter((intent) => intent.lifecycle_state === stateFilter);
}

/**
 * Helper function to search order intents by symbol query.
 */
export function searchOrderIntentsBySymbol(
  intents: readonly OrderIntentPayload[],
  searchQuery: string
): OrderIntentPayload[] {
  const cleanQuery = searchQuery.trim().toUpperCase();
  if (!cleanQuery) {
    return [...intents];
  }
  return intents.filter((intent) => intent.symbol.toUpperCase().includes(cleanQuery));
}

/**
 * Helper function to transition an in-memory OrderIntent (frontend preview adapter).
 * Enforces legal state transitions: STAGED -> CANCELLED, REJECTED, or EXPIRED.
 */
export function transitionOrderIntentState(
  intent: OrderIntentPayload,
  targetState: OrderLifecycleState,
  reason?: string
): OrderIntentPayload {
  if (intent.is_terminal || intent.lifecycle_state !== "STAGED") {
    throw new Error(`Cannot transition order intent from terminal or non-staged state '${intent.lifecycle_state}'`);
  }
  if (targetState === "STAGED") {
    throw new Error("Cannot transition order intent back to STAGED state");
  }

  return {
    ...intent,
    lifecycle_state: targetState,
    is_staged: false,
    is_terminal: true,
    rejection_reason: reason ?? intent.rejection_reason ?? null,
  };
}

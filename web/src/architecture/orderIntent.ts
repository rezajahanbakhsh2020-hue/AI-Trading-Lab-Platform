/**
 * Frontend domain contract and lifecycle types for Order Intent (Project 2 Foundation).
 * Represents an authorized staged order intent.
 * DOES NOT represent routed, filled, or broker-executed orders.
 */

export type OrderLifecycleState = "STAGED" | "REJECTED" | "CANCELLED" | "EXPIRED";

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
}

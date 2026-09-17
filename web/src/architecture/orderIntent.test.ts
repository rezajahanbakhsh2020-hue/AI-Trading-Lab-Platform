import { describe, expect, it } from "vitest";
import {
  filterOrderIntentsByState,
  searchOrderIntentsBySymbol,
  transitionOrderIntentState,
  type OrderIntentPayload,
} from "./orderIntent";

const sampleIntents: OrderIntentPayload[] = [
  {
    order_intent_id: "ord_101",
    authorization_id: "auth_101",
    user_id: "user_a",
    symbol: "XAUUSD",
    direction: "buy",
    order_type: "market",
    requested_price: 2650.0,
    requested_quantity: 1.0,
    stop_loss: 2635.0,
    take_profit_1: 2670.0,
    idempotency_key: "idemp_101",
    creation_timestamp: 1700000000,
    lifecycle_state: "STAGED",
    is_staged: true,
    is_terminal: false,
  },
  {
    order_intent_id: "ord_102",
    authorization_id: "auth_102",
    user_id: "user_a",
    symbol: "EURUSD",
    direction: "sell",
    order_type: "limit",
    requested_price: 1.085,
    requested_quantity: 2.0,
    stop_loss: 1.091,
    take_profit_1: 1.079,
    idempotency_key: "idemp_102",
    creation_timestamp: 1700000100,
    lifecycle_state: "CANCELLED",
    is_staged: false,
    is_terminal: true,
  },
];

describe("orderIntent architecture helpers", () => {
  it("filters order intents by lifecycle state", () => {
    expect(filterOrderIntentsByState(sampleIntents, "ALL")).toHaveLength(2);
    expect(filterOrderIntentsByState(sampleIntents, "STAGED")).toHaveLength(1);
    expect(filterOrderIntentsByState(sampleIntents, "STAGED")[0].order_intent_id).toBe("ord_101");
    expect(filterOrderIntentsByState(sampleIntents, "EXPIRED")).toHaveLength(0);
  });

  it("searches order intents by symbol", () => {
    expect(searchOrderIntentsBySymbol(sampleIntents, "xau")).toHaveLength(1);
    expect(searchOrderIntentsBySymbol(sampleIntents, "xau")[0].symbol).toBe("XAUUSD");
    expect(searchOrderIntentsBySymbol(sampleIntents, "")).toHaveLength(2);
  });

  it("transitions order intent state legally", () => {
    const updated = transitionOrderIntentState(sampleIntents[0], "CANCELLED", "User cancelled");
    expect(updated.lifecycle_state).toBe("CANCELLED");
    expect(updated.is_staged).toBe(false);
    expect(updated.is_terminal).toBe(true);
    expect(updated.rejection_reason).toBe("User cancelled");
  });

  it("throws error on illegal state transition from terminal state", () => {
    expect(() => transitionOrderIntentState(sampleIntents[1], "EXPIRED")).toThrow(
      "Cannot transition order intent from terminal or non-staged state"
    );
  });
});

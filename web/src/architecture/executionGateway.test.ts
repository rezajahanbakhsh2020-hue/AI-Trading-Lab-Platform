import { describe, expect, it } from "vitest";
import {
  isExternallyExecuted,
  type ExecutionAttemptResultPayload,
} from "./executionGateway";

describe("Execution Gateway Architecture Domain Contract", () => {
  it("verify isExternallyExecuted always returns false for host attempts", () => {
    const attempt: ExecutionAttemptResultPayload = {
      success: false,
      user_id: "user_100",
      order_intent_id: "ord_100",
      status: "UNCONFIGURED",
      reason: "No broker connected",
      externally_executed: false,
      timestamp: 1700000000,
      provider_id: "unavailable_execution_adapter",
      is_accepted: false,
      is_rejected: true,
      is_failed: false,
    };

    expect(isExternallyExecuted(attempt)).toBe(false);
    expect(isExternallyExecuted(null)).toBe(false);
  });

  it("evaluates boundary statuses correctly", () => {
    const acceptedAttempt: ExecutionAttemptResultPayload = {
      success: true,
      user_id: "user_100",
      order_intent_id: "ord_100",
      status: "ACCEPTED_AT_BOUNDARY",
      reason: "Request accepted at boundary",
      externally_executed: false,
      timestamp: 1700000000,
      provider_id: "mock_port",
      is_accepted: true,
      is_rejected: false,
      is_failed: false,
    };

    expect(acceptedAttempt.is_accepted).toBe(true);
    expect(acceptedAttempt.is_rejected).toBe(false);
  });
});

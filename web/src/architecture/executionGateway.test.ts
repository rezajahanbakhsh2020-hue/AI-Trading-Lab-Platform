import { describe, expect, it, vi } from "vitest";
import {
  isExternallyExecuted,
  requestExecutionApi,
  reconcileExecutionApi,
  fetchExecutionBoundaryStatusApi,
  fetchOrderIntentsApi,
  updateOrderIntentStateApi,
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

  it("fetches order intents via API helper", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          success: true,
          order_intents: [
            {
              order_intent_id: "ord_100",
              lifecycle_state: "STAGED",
              symbol: "XAUUSD",
            },
          ],
        }),
      })
    );

    const res = await fetchOrderIntentsApi("mock_token", "XAUUSD", "STAGED");
    expect(res.success).toBe(true);
    expect(res.order_intents?.length).toBe(1);
    expect(res.order_intents?.[0].order_intent_id).toBe("ord_100");
    vi.unstubAllGlobals();
  });

  it("fetches boundary status via API helper", async () => {
    const mockBoundary = {
      boundary_name: "Project 2 Execution Gateway Boundary",
      status: "configured",
      allows_execution: false,
      provider: { provider_id: "mock", configured: true, connected: true, allows_execution: false, message: "OK" },
      notice: "Test notice",
    };

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, boundary: mockBoundary }),
      })
    );

    const res = await fetchExecutionBoundaryStatusApi("mock_token");
    expect(res.success).toBe(true);
    expect(res.boundary?.boundary_name).toBe("Project 2 Execution Gateway Boundary");
    vi.unstubAllGlobals();
  });

  it("submits execution request via API helper", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          success: false,
          attempt: {
            success: false,
            order_intent_id: "ord_100",
            status: "FAILED_AT_BOUNDARY",
            externally_executed: false,
          },
        }),
      })
    );

    const res = await requestExecutionApi("ord_100", "mock_token");
    expect(res.attempt?.order_intent_id).toBe("ord_100");
    expect(res.attempt?.externally_executed).toBe(false);
    vi.unstubAllGlobals();
  });

  it("reconciles execution via API helper", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          success: true,
          reconciliation: {
            reconciliation_id: "rec_1",
            order_intent_id: "ord_100",
            status: "NOT_CONFIGURED",
            externally_executed: false,
          },
        }),
      })
    );

    const res = await reconcileExecutionApi("ord_100", "mock_token");
    expect(res.success).toBe(true);
    expect(res.reconciliation?.status).toBe("NOT_CONFIGURED");
    vi.unstubAllGlobals();
  });

  it("updates order intent state via API helper", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          success: true,
          order_intent: {
            order_intent_id: "ord_100",
            lifecycle_state: "CANCELLED",
          },
        }),
      })
    );

    const res = await updateOrderIntentStateApi("ord_100", "CANCELLED", "User cancelled", "mock_token");
    expect(res.success).toBe(true);
    expect(res.order_intent?.lifecycle_state).toBe("CANCELLED");
    vi.unstubAllGlobals();
  });
});

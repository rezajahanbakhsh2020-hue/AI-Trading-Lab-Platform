import { describe, expect, it, vi } from "vitest";
import {
  isExternallyExecuted,
  requestExecutionApi,
  requestCanonicalOrderIntentApi,
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

  it("requests canonical order intent via requestCanonicalOrderIntentApi helper without client trading parameters", async () => {
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        order_intent: {
          order_intent_id: "ord_canonical_100",
          publication_id: "pub_100",
          symbol: "XAUUSD",
          direction: "buy",
          requested_price: 2650.5,
          stop_loss: 2635.0,
          take_profit_1: 2670.0,
          lifecycle_state: "STAGED",
        },
      }),
    });
    vi.stubGlobal("fetch", fetchSpy);

    const pubId = "pub_100";
    const idempKey = "ui_user_1_pub_100";
    const token = "mock_session_token";

    const res = await requestCanonicalOrderIntentApi(pubId, idempKey, token);

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, options] = fetchSpy.mock.calls[0];

    expect(url).toBe("/api/v1/execution/canonical-intent");
    expect(options.method).toBe("POST");
    expect(options.headers["Authorization"]).toBe("Bearer mock_session_token");

    const parsedBody = JSON.parse(options.body);
    expect(parsedBody).toEqual({
      publication_id: "pub_100",
      idempotency_key: "ui_user_1_pub_100",
    });

    // Explicitly verify no trading or pricing parameters are sent in the request payload
    expect(parsedBody.entry_price).toBeUndefined();
    expect(parsedBody.requested_price).toBeUndefined();
    expect(parsedBody.stop_loss).toBeUndefined();
    expect(parsedBody.take_profit_1).toBeUndefined();
    expect(parsedBody.symbol).toBeUndefined();
    expect(parsedBody.direction).toBeUndefined();
    expect(parsedBody.requested_quantity).toBeUndefined();

    expect(res.success).toBe(true);
    expect(res.order_intent?.order_intent_id).toBe("ord_canonical_100");
    expect(res.order_intent?.publication_id).toBe("pub_100");
    expect(res.order_intent?.requested_price).toBe(2650.5);

    vi.unstubAllGlobals();
  });
});

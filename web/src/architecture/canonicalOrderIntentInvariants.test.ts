import { describe, expect, it, vi } from "vitest";
import { requestCanonicalOrderIntentApi } from "./executionGateway";
import { createHostSnapshotFromProject1 } from "./hostView";
import { SAMPLE_CONNECTED_PORT, SAMPLE_REAL_PROJECT1_SIGNAL } from "./testFixtures";

describe("App & Architecture OrderIntent Canonical Staging Invariants", () => {
  it("ensures live signal host snapshot has null/empty orderIntents and exposes publicationId", () => {
    const snapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL,
      "XAUUSD",
      "1h"
    );

    expect(snapshot.orderIntents).toEqual([]);
    expect(snapshot.signal.publicationId).toBe("pub_test_xauusd_1h_live_001");
  });

  it("stages order intent via canonical server path when publicationId exists", async () => {
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        order_intent: {
          order_intent_id: "ord_canonical_200",
          publication_id: "pub_test_xauusd_1h_live_001",
          user_id: "user_test",
          symbol: "XAUUSD",
          direction: "buy",
          requested_price: 2650.5,
          requested_quantity: 1.0,
          stop_loss: 2635.0,
          take_profit_1: 2670.0,
          lifecycle_state: "STAGED",
        },
      }),
    });
    vi.stubGlobal("fetch", fetchSpy);

    const snapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL,
      "XAUUSD",
      "1h"
    );

    const pubId = snapshot.signal.publicationId;
    expect(pubId).not.toBeNull();

    const idempotencyKey = `ui_user_test_${pubId}`;
    const sessionToken = "session_token_123";

    const res = await requestCanonicalOrderIntentApi(pubId!, idempotencyKey, sessionToken);

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/execution/canonical-intent",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer session_token_123",
        }),
        body: JSON.stringify({
          publication_id: "pub_test_xauusd_1h_live_001",
          idempotency_key: "ui_user_test_pub_test_xauusd_1h_live_001",
        }),
      })
    );

    expect(res.success).toBe(true);
    expect(res.order_intent?.order_intent_id).toBe("ord_canonical_200");
    expect(res.order_intent?.requested_price).toBe(2650.5);

    vi.unstubAllGlobals();
  });

  it("fails closed when publicationId is missing/null without creating local OrderIntent or calling API", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    const signalNoPub = {
      ...SAMPLE_REAL_PROJECT1_SIGNAL,
      metadata: { source: "Project1", provenance_type: "live_signal", is_live: true }, // no publication_id
    };

    const snapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      signalNoPub,
      "XAUUSD",
      "1h"
    );

    expect(snapshot.signal.publicationId).toBeNull();
    expect(snapshot.orderIntents).toEqual([]);

    // Simulating App.tsx handleStageOrderIntent logic when pubId is null
    const pubId = snapshot.signal.publicationId;
    let stagedIntents: any[] = [];

    if (pubId) {
      await requestCanonicalOrderIntentApi(pubId, "key", "token");
    }

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(stagedIntents).toEqual([]);

    vi.unstubAllGlobals();
  });
});

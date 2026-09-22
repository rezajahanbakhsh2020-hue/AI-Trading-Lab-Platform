import { describe, it, expect } from "vitest";
import {
  extractTimelineFromHostSnapshot,
  generateExplainabilityPayload,
} from "./timeline";
import {
  createDisconnectedHostSnapshot,
  createHostSnapshotFromProject1,
} from "./hostView";
import {
  SAMPLE_CONNECTED_PORT,
  SAMPLE_REAL_PROJECT1_SIGNAL,
} from "./testFixtures";

describe("Timeline & Explainability Architecture", () => {
  it("extracts chronological timeline items from connected snapshot", () => {
    const snapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL
    );

    const items = extractTimelineFromHostSnapshot(snapshot);
    expect(items.length).toBeGreaterThan(0);

    const sigItem = items.find((it) => it.category === "signal");
    expect(sigItem).toBeDefined();
    expect(sigItem?.explainable).toBe(true);
    expect(sigItem?.title).toContain("BUY");
  });

  it("handles disconnected snapshot gracefully with warning states", () => {
    const snapshot = createDisconnectedHostSnapshot();
    const items = extractTimelineFromHostSnapshot(snapshot);

    const mktItem = items.find((it) => it.category === "market");
    expect(mktItem).toBeDefined();
    expect(mktItem?.severity).toBe("warning");
  });

  it("generates explainability payload and redacts protected parameters", () => {
    const snapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL
    );
    const items = extractTimelineFromHostSnapshot(snapshot);
    const sigItem = items.find((it) => it.category === "signal")!;

    const explain = generateExplainabilityPayload(sigItem, snapshot);
    expect(explain.itemId).toBe(sigItem.itemId);
    expect(explain.source).toBe("Project1GatewayAdapter");
    expect(explain.permittedMarketContext.symbol).toBe("XAUUSD");
    expect(explain.permittedRiskContext.entryPrice).toBe(2650.5);
    expect(explain.explainabilityNotes.length).toBeGreaterThan(0);
  });
});

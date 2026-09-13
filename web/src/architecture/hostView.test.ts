import { describe, expect, it } from "vitest";
import {
  DISCONNECTED_MESSAGE,
  PRIMARY_MARKET,
  createDisconnectedHostSnapshot,
} from "./hostView";

describe("disconnected host snapshot", () => {
  const snapshot = createDisconnectedHostSnapshot();

  it("keeps Project 1 disconnected", () => {
    expect(snapshot.project1.connected).toBe(false);
    expect(snapshot.project1.status).toBe("disconnected");
    expect(snapshot.project1.port).toBe("Project1IntegrationPort");
    expect(snapshot.project1.message).toBe(DISCONNECTED_MESSAGE);
  });

  it("does not fabricate market, signal, or risk data", () => {
    expect(snapshot.market.symbol).toBe(PRIMARY_MARKET);
    expect(snapshot.market.quote).toBeNull();
    expect(snapshot.market.change).toBeNull();
    expect(snapshot.market.volume).toBeNull();
    expect(snapshot.market.candles).toEqual([]);
    expect(snapshot.signal.action).toBeNull();
    expect(snapshot.strategy.name).toBeNull();
    expect(snapshot.risk.entry).toBeNull();
    expect(snapshot.risk.stopLoss).toBeNull();
    expect(snapshot.risk.takeProfits).toEqual([]);
    expect(snapshot.activity).toEqual([]);
    expect(snapshot.generatedAt).toBeNull();
  });

  it("marks operational surfaces unavailable instead of inventing values", () => {
    expect(snapshot.market.status).toBe("unavailable");
    expect(snapshot.strategy.status).toBe("unavailable");
    expect(snapshot.signal.status).toBe("unavailable");
    expect(snapshot.performance.status).toBe("unavailable");
    expect(snapshot.risk.status).toBe("unavailable");
    expect(snapshot.monitoring.status).toBe("unavailable");
    expect(snapshot.providers.marketData).toBe("unconnected");
  });
});

import { describe, expect, it } from "vitest";
import {
  DISCONNECTED_MESSAGE,
  PRIMARY_MARKET,
  SAMPLE_CONNECTED_PORT,
  SAMPLE_REAL_PROJECT1_SIGNAL,
  createDisconnectedHostSnapshot,
  createHostSnapshotFromProject1,
} from "./hostView";

describe("disconnected host snapshot", () => {
  const snapshot = createDisconnectedHostSnapshot();

  it("keeps Project 1 disconnected", () => {
    expect(snapshot.project1.connected).toBe(false);
    expect(snapshot.project1.status).toBe("disconnected");
    expect(snapshot.project1.port).toBe("Project1IntegrationPort");
    expect(snapshot.project1.adapterName).toBe("DisconnectedProject1Adapter");
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

describe("connected Project 1 host snapshot", () => {
  it("maps real Project 1 signal and trade setup outputs into clean host snapshot", () => {
    const snapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL
    );

    expect(snapshot.project1.connected).toBe(true);
    expect(snapshot.project1.status).toBe("connected");
    expect(snapshot.project1.adapterName).toBe("Project1LabArtifactAdapter");
    expect(snapshot.project1.port).toBe("Project1IntegrationPort");

    expect(snapshot.signal.action).toBe("BUY");
    expect(snapshot.signal.signalId).toBe("p1_xauusd_1h_1700000000");
    expect(snapshot.signal.confidence).toBe(0.88);
    expect(snapshot.signal.strategyName).toBe("GoldTrendv1");
    expect(snapshot.signal.status).toBe("active");

    expect(snapshot.risk.entry).toBe(2650.5);
    expect(snapshot.risk.stopLoss).toBe(2635.0);
    expect(snapshot.risk.takeProfits).toEqual([2670.0, 2690.0, 2710.0]);
    expect(snapshot.risk.status).toBe("available");

    expect(snapshot.strategy.name).toBe("GoldTrendv1");
    expect(snapshot.strategy.stability).toBe(88);
    expect(snapshot.strategy.status).toBe("active");
  });

  it("handles connected Project 1 emitting no active signal (empty signal state)", () => {
    const snapshot = createHostSnapshotFromProject1(SAMPLE_CONNECTED_PORT, null, "XAUUSD", "1h");

    expect(snapshot.project1.connected).toBe(true);
    expect(snapshot.signal.action).toBe("NO SIGNAL");
    expect(snapshot.signal.status).toBe("no-signal");
    expect(snapshot.risk.entry).toBeNull();
    expect(snapshot.risk.status).toBe("unavailable");
  });

  it("falls back to disconnected snapshot if port is reported disconnected", () => {
    const snapshot = createHostSnapshotFromProject1(
      { name: "DisconnectedAdapter", port: "Project1IntegrationPort", connected: false },
      SAMPLE_REAL_PROJECT1_SIGNAL
    );

    expect(snapshot.project1.connected).toBe(false);
    expect(snapshot.project1.status).toBe("disconnected");
    expect(snapshot.signal.action).toBeNull();
  });
});

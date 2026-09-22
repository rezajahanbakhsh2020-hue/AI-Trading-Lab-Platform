import { describe, expect, it } from "vitest";
import {
  DISCONNECTED_MESSAGE,
  PRIMARY_MARKET,
  PROJECT1_GATEWAY_PORT,
  createDisconnectedHostSnapshot,
  createHostSnapshotFromProject1,
} from "./hostView";
import { SAMPLE_CONNECTED_PORT, SAMPLE_REAL_PROJECT1_SIGNAL } from "./testFixtures";
import { SAMPLE_BIQUOTE_PROVIDER, SAMPLE_BIQUOTE_QUOTE_XAUUSD, SAMPLE_BIQUOTE_CANDLES_XAUUSD } from "./marketData";

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
    expect(snapshot.market.candles).toEqual([]);
    expect(snapshot.signal.action).toBeNull();
    expect(snapshot.strategy.name).toBeNull();
    expect(snapshot.risk.entry).toBeNull();
    expect(snapshot.risk.stopLoss).toBeNull();
    expect(snapshot.risk.takeProfits).toEqual([]);
    expect(snapshot.activity).toEqual([]);
    expect(snapshot.generatedAt).toBeNull();
  });

  it("marks operational surfaces unavailable/disconnected instead of inventing values", () => {
    expect(snapshot.market.status).toBe("disconnected");
    expect(snapshot.strategy.status).toBe("unavailable");
    expect(snapshot.signal.status).toBe("unavailable");
    expect(snapshot.performance.status).toBe("unavailable");
    expect(snapshot.risk.status).toBe("unavailable");
    expect(snapshot.monitoring.status).toBe("unavailable");
    expect(snapshot.providers.marketData).toBe("disconnected");
  });
});

describe("connected Project 1 host snapshot", () => {
  it("maps real Project 1 signal, market data, and trade setup outputs into clean host snapshot", () => {
    const marketState = {
      symbol: "XAUUSD",
      timeframe: "1h",
      provider: SAMPLE_BIQUOTE_PROVIDER,
      quote: SAMPLE_BIQUOTE_QUOTE_XAUUSD,
      candles: SAMPLE_BIQUOTE_CANDLES_XAUUSD,
      status: "connected" as const,
      message: "Streaming live market data via BiQuoteProvider.",
      lastFetchedAt: "2024-03-09T10:00:00Z",
    };

    const snapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL,
      "XAUUSD",
      "1h",
      marketState
    );

    expect(snapshot.project1.connected).toBe(true);
    expect(snapshot.project1.status).toBe("connected");
    expect(snapshot.project1.adapterName).toBe("Project1GatewayAdapter");
    expect(snapshot.project1.port).toBe("Project1IntegrationPort");

    expect(snapshot.market.status).toBe("connected");
    expect(snapshot.market.provider?.name).toBe("BiQuoteProvider");
    expect(snapshot.market.quote?.last).toBe(2663.0);
    expect(snapshot.market.candles.length).toBe(SAMPLE_BIQUOTE_CANDLES_XAUUSD.length);

    expect(snapshot.signal.action).toBe("BUY");
    expect(snapshot.signal.signalId).toBe("p1_xauusd_1h_live_current");
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

  it("returns truthful no-signal status and holds risk levels when historical/stale XAUUSD signal (>300s old or lab_artifact) is passed", () => {
    const staleSignal = {
      signal_id: "p1_xauusd_1h_1700000000",
      symbol: "XAUUSD",
      signal_type: "buy",
      timestamp: 1700000000, // Nov 2023
      entry_price: 2650.5,
      stop_loss: 2635.0,
      take_profits: [2670.0, 2690.0, 2710.0],
      confidence: 0.88,
      strategy_name: "GoldTrendv1",
      timeframe: "1h",
      metadata: { provenance_type: "lab_artifact" },
    };

    const snapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      staleSignal,
      "XAUUSD",
      "1h"
    );

    expect(snapshot.signal.status).toBe("no-signal");
    expect(snapshot.signal.action).toBe("NO SIGNAL");
    expect(snapshot.signal.signalId).toBeNull();
    expect(snapshot.project1.adapterName).toBe("Project1GatewayAdapter");
    expect(snapshot.risk.status).toBe("unavailable");
    expect(snapshot.risk.entry).toBeNull();
    expect(snapshot.orderIntents).toEqual([]);
  });
});

describe("signal purity and fail-closed runtime verification", () => {
  it("ensures a runtime with zero Project 1 Gateway records displays NO SIGNAL and null trade setup levels", () => {
    const snapshot = createHostSnapshotFromProject1(PROJECT1_GATEWAY_PORT, null, "XAUUSD", "1h");

    expect(snapshot.project1.connected).toBe(true);
    expect(snapshot.project1.adapterName).toBe("Project1GatewayAdapter");
    expect(snapshot.signal.action).toBe("NO SIGNAL");
    expect(snapshot.signal.status).toBe("no-signal");
    expect(snapshot.signal.signalId).toBeNull();
    expect(snapshot.risk.entry).toBeNull();
    expect(snapshot.risk.stopLoss).toBeNull();
    expect(snapshot.risk.takeProfits).toEqual([]);
    expect(snapshot.risk.status).toBe("unavailable");
  });

  it("ensures production PROJECT1_GATEWAY_PORT does not contain hardcoded sample signals", () => {
    expect(PROJECT1_GATEWAY_PORT.name).toBe("Project1GatewayAdapter");
    expect(PROJECT1_GATEWAY_PORT.port).toBe("Project1IntegrationPort");
    expect(PROJECT1_GATEWAY_PORT.connected).toBe(true);
    // Verify no trading signal values exist on gateway port payload
    expect((PROJECT1_GATEWAY_PORT as any).entry_price).toBeUndefined();
    expect((PROJECT1_GATEWAY_PORT as any).signal_type).toBeUndefined();
  });

  it("ensures sample, lab, or backtest artifact data cannot be converted into live_signal in connected state", () => {
    const labArtifactSignal = {
      signal_id: "lab_artifact_xauusd_001",
      symbol: "XAUUSD",
      signal_type: "buy",
      timestamp: Math.floor(Date.now() / 1000), // recent timestamp
      entry_price: 2650.5,
      stop_loss: 2635.0,
      take_profits: [2670.0, 2690.0, 2710.0],
      confidence: 0.90,
      strategy_name: "LabArtifactStrategy",
      timeframe: "1h",
      metadata: { provenance_type: "lab_artifact", is_historical: true },
    };

    const snapshot = createHostSnapshotFromProject1(
      PROJECT1_GATEWAY_PORT,
      labArtifactSignal,
      "XAUUSD",
      "1h"
    );

    expect(snapshot.signal.status).toBe("no-signal");
    expect(snapshot.signal.action).toBe("NO SIGNAL");
    expect(snapshot.risk.entry).toBeNull();
    expect(snapshot.risk.stopLoss).toBeNull();
    expect(snapshot.risk.takeProfits).toEqual([]);
  });

  it("verifies test fixtures in testFixtures.ts remain functional for test suites", () => {
    expect(SAMPLE_CONNECTED_PORT.connected).toBe(true);
    expect(SAMPLE_REAL_PROJECT1_SIGNAL.signal_id).toBe("p1_xauusd_1h_live_current");
    expect(SAMPLE_REAL_PROJECT1_SIGNAL.entry_price).toBe(2650.5);

    const fixtureSnapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL,
      "XAUUSD",
      "1h"
    );
    expect(fixtureSnapshot.signal.action).toBe("BUY");
    expect(fixtureSnapshot.risk.entry).toBe(2650.5);
  });
});

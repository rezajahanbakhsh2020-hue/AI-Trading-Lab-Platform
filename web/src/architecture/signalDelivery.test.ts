import { describe, it, expect, beforeEach } from "vitest";
import {
  evaluateDeliveryAuthorization,
  executeSignalDeliveryDispatch,
  getSampleOutboundChannels,
  loadSignalDeliveryHistory,
  saveSignalDeliveryRecord,
  type SignalDeliveryPolicy,
} from "./signalDelivery";
import {
  createDisconnectedHostSnapshot,
  createHostSnapshotFromProject1,
} from "./hostView";
import {
  SAMPLE_CONNECTED_PORT,
  SAMPLE_REAL_PROJECT1_SIGNAL,
} from "./testFixtures";

describe("Signal Delivery Architecture Layer", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("evaluates authorization policy correctly", () => {
    const validPolicy: SignalDeliveryPolicy = {
      consumerId: "user_01",
      hasReadSignalsPermission: true,
      hasReadSetupPermission: true,
      deliveryEnabled: true,
      allowedSymbols: ["XAUUSD"],
      allowedStrategies: ["GoldTrendv1"],
    };

    expect(evaluateDeliveryAuthorization(validPolicy, "XAUUSD", "GoldTrendv1").authorized).toBe(true);

    const noPermPolicy = { ...validPolicy, hasReadSignalsPermission: false };
    expect(evaluateDeliveryAuthorization(noPermPolicy, "XAUUSD", "GoldTrendv1").authorized).toBe(false);

    const disabledPolicy = { ...validPolicy, deliveryEnabled: false };
    expect(evaluateDeliveryAuthorization(disabledPolicy, "XAUUSD", "GoldTrendv1").authorized).toBe(false);

    const invalidSymbolPolicy = { ...validPolicy, allowedSymbols: ["EURUSD"] };
    expect(evaluateDeliveryAuthorization(invalidSymbolPolicy, "XAUUSD", "GoldTrendv1").authorized).toBe(false);
  });

  it("returns NOT_DELIVERED when host snapshot is disconnected", () => {
    const disconnectedSnapshot = createDisconnectedHostSnapshot();
    const result = executeSignalDeliveryDispatch(disconnectedSnapshot, "telegram");

    expect(result.status).toBe("NOT_DELIVERED");
    expect(result.reason).toContain("disconnected");
  });

  it("executes successful delivery dispatch when connected with active signal", () => {
    const connectedSnapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL
    );
    const result = executeSignalDeliveryDispatch(connectedSnapshot, "telegram", "user_01");

    expect(result.status).toBe("DELIVERED");
    expect(result.action).toBe("BUY");
    expect(result.symbol).toBe("XAUUSD");
    expect(result.channel).toBe("telegram");
  });

  it("masks trade setup details if user lacks READ_TRADE_SETUPS permission", () => {
    const restrictedSnapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL,
      "XAUUSD",
      "1h",
      {},
      {
        userId: "guest_user",
        role: "user",
        permissions: ["read:signals"],
        isAdmin: false,
      }
    );

    const result = executeSignalDeliveryDispatch(restrictedSnapshot, "telegram", "guest_user");

    expect(result.status).toBe("DELIVERED");
    expect(result.redacted).toBe(true);
    expect(result.detail).toContain("masked for restricted user role");
  });

  it("persists and loads delivery records in localStorage", () => {
    const record = executeSignalDeliveryDispatch(
      createHostSnapshotFromProject1(SAMPLE_CONNECTED_PORT, SAMPLE_REAL_PROJECT1_SIGNAL),
      "in_app",
      "user_test"
    );

    saveSignalDeliveryRecord("user_test", record);
    const loaded = loadSignalDeliveryHistory("user_test");

    expect(loaded.length).toBe(1);
    expect(loaded[0].id).toBe(record.id);
    expect(loaded[0].channel).toBe("in_app");
  });

  it("returns sample outbound channels with proper setup requirements", () => {
    const snapshot = createDisconnectedHostSnapshot();
    const channels = getSampleOutboundChannels(snapshot);

    expect(channels.length).toBe(3);
    expect(channels.find((c) => c.channelId === "telegram")?.enabled).toBe(true);
  });
});

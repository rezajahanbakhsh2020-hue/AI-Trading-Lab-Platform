import { describe, it, expect, beforeEach } from "vitest";
import {
  loadUserAlertRules,
  saveUserAlertRules,
  syncAlertsFromHostSnapshot,
  countActiveAlerts,
  createDefaultAlertRules,
  type MarketAlertItem,
} from "./alert";
import { createDisconnectedHostSnapshot } from "./hostView";

describe("Alert Architecture & Storage", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("loads default alert rules when localStorage is empty", () => {
    const rules = loadUserAlertRules("user_1");
    expect(rules.length).toBeGreaterThan(0);
    expect(rules[0].symbol).toBe("XAUUSD");
  });

  it("persists and loads custom alert rules", () => {
    const customRules = [
      {
        ruleId: "rule_test",
        kind: "price" as const,
        symbol: "EURUSD",
        conditionType: "price_above" as const,
        threshold: 1.12,
        timeframe: "1h",
        enabled: true,
        createdAt: new Date().toISOString(),
      },
    ];
    saveUserAlertRules("user_2", customRules);
    const loaded = loadUserAlertRules("user_2");
    expect(loaded).toHaveLength(1);
    expect(loaded[0].ruleId).toBe("rule_test");
  });

  it("syncs freshness alerts when disconnected snapshot is passed", () => {
    const snapshot = createDisconnectedHostSnapshot("XAUUSD");
    const rules = createDefaultAlertRules("XAUUSD");
    const alerts = syncAlertsFromHostSnapshot("user_3", snapshot, [], rules);

    expect(alerts.length).toBeGreaterThan(0);
    const discAlert = alerts.find((a) => a.kind === "freshness" && a.severity === "critical");
    expect(discAlert).toBeDefined();
    expect(discAlert?.symbol).toBe("XAUUSD");
  });

  it("counts active alerts correctly", () => {
    const alerts: MarketAlertItem[] = [
      {
        id: "a1",
        kind: "price",
        severity: "warning",
        status: "active",
        message: "Test 1",
        symbol: "XAUUSD",
        timeframe: "1h",
        createdAt: new Date().toISOString(),
      },
      {
        id: "a2",
        kind: "signal",
        severity: "info",
        status: "resolved",
        message: "Test 2",
        symbol: "XAUUSD",
        timeframe: "1h",
        createdAt: new Date().toISOString(),
      },
    ];
    expect(countActiveAlerts(alerts)).toBe(1);
  });
});

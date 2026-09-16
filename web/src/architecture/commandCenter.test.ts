import { describe, it, expect, beforeEach } from "vitest";
import {
  queryCommandCenter,
  loadRecentSearches,
  saveRecentSearch,
  clearRecentSearches,
} from "./commandCenter";
import type { HostSnapshot } from "./hostView";

const mockSnapshot: HostSnapshot = {
  generatedAt: null,
  platform: { name: "Platform", status: "ready", role: "Host application" },
  project1: { connected: true, port: "Port1", adapterName: "LabAdapter", status: "ready", message: "Connected" },
  market: {
    symbol: "XAUUSD",
    timeframe: "1h",
    status: "connected",
    provider: { id: "p1", name: "BiQuote", provider: "biquote", status: "connected", supportedTimeframes: ["1h"] },
    quote: { symbol: "XAUUSD", last: 2000, changePercent: 0.5, timestamp: 123456789 },
    candles: [],
    message: "Live",
    lastFetchedAt: null,
  },
  strategy: { name: "GoldStrategy", stability: 85, status: "active", message: "Active" },
  signal: { signalId: "sig_001", action: "BUY", timestamp: "123456789", confidence: 0.85, status: "ready", message: "Active signal" },
  risk: { entry: 2000, stopLoss: 1980, takeProfits: [2040, 2080], status: "available", message: "Calculated" },
  monitoring: { freshness: "Fresh", health: "healthy", status: "ready", message: "Ok" },
  providers: { marketData: "connected", quote: "connected", message: "Providers ready" },
  performance: { status: "unavailable", message: "No perf data" },
  security: { userId: "test_user", role: "user", isAdmin: false, permissions: ["read:signals"], status: "enforced", message: "Authorized" },
  authorization: {
    status: "AUTHORIZED",
    isAuthorized: true,
    reason: "autonomous execution authorized",
    checks: [],
    riskRewardRatio: 2.0,
    timestamp: 123456789,
  },
  activity: [],
};

describe("commandCenter architecture", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("returns default navigation groups for empty search query", () => {
    const result = queryCommandCenter("", mockSnapshot);
    expect(result.length).toBeGreaterThan(0);
    const navGroup = result.find((g) => g.category === "navigation");
    expect(navGroup).toBeDefined();
    expect(navGroup?.items.length).toBeGreaterThan(5);
  });

  it("filters items correctly based on search query", () => {
    const result = queryCommandCenter("xau", mockSnapshot);
    const mktGroup = result.find((g) => g.category === "market");
    expect(mktGroup).toBeDefined();
    expect(mktGroup?.items.some((i) => i.title === "XAUUSD")).toBe(true);
  });

  it("hides admin-only strategy research for normal users", () => {
    const result = queryCommandCenter("research", mockSnapshot);
    const allItems = result.flatMap((g) => g.items);
    expect(allItems.some((i) => i.requiresAdmin)).toBe(false);
  });

  it("shows admin-only strategy research for admin users", () => {
    const adminSnapshot: HostSnapshot = {
      ...mockSnapshot,
      security: { ...mockSnapshot.security, role: "admin", isAdmin: true },
    };
    const result = queryCommandCenter("research", adminSnapshot);
    const allItems = result.flatMap((g) => g.items);
    expect(allItems.some((i) => i.requiresAdmin)).toBe(true);
  });

  it("manages recent searches persistence in localStorage", () => {
    expect(loadRecentSearches()).toEqual([]);
    saveRecentSearch("XAUUSD");
    saveRecentSearch("EURUSD");
    expect(loadRecentSearches()).toEqual(["EURUSD", "XAUUSD"]);
    clearRecentSearches();
    expect(loadRecentSearches()).toEqual([]);
  });
});

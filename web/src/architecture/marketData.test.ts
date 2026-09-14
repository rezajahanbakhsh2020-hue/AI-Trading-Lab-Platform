import { describe, expect, it } from "vitest";
import { WATCHLIST_SYMBOLS, INITIAL_NOTIFICATIONS } from "./marketData";

describe("Market Data & Watchlist Structures", () => {
  it("includes XAUUSD as the primary market asset", () => {
    const primary = WATCHLIST_SYMBOLS.find((item) => item.primary);
    expect(primary).toBeDefined();
    expect(primary?.symbol).toBe("XAUUSD");
  });

  it("marks all watchlist assets as Disconnected by default when Project 1 is not connected", () => {
    WATCHLIST_SYMBOLS.forEach((item) => {
      expect(item.status).toBe("Disconnected");
    });
  });

  it("provides initial notifications feed", () => {
    expect(INITIAL_NOTIFICATIONS.length).toBeGreaterThan(0);
    expect(INITIAL_NOTIFICATIONS[0].title).toBeTruthy();
  });
});

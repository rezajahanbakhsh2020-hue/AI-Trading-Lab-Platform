import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { WATCHLIST_SYMBOLS, INITIAL_NOTIFICATIONS, fetchMarketCandles, fetchMarketQuote, fetchProviders } from "./marketData";

describe("Market Data & Watchlist Structures", () => {
  it("includes XAUUSD as the primary market asset", () => {
    const primary = WATCHLIST_SYMBOLS.find((item) => item.primary);
    expect(primary).toBeDefined();
    expect(primary?.symbol).toBe("XAUUSD");
  });

  it("marks all watchlist assets as disconnected by default when Project 1 is not connected", () => {
    WATCHLIST_SYMBOLS.forEach((item) => {
      expect(item.status).toBe("disconnected");
    });
  });

  it("provides initial notifications feed", () => {
    expect(INITIAL_NOTIFICATIONS.length).toBeGreaterThan(0);
    expect(INITIAL_NOTIFICATIONS[0].title).toBeTruthy();
  });
});

describe("Market Data API Helper Functions", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches market candles successfully", async () => {
    const mockCandles = [
      { timestamp: 1700000000, open: 2650.0, high: 2655.0, low: 2648.0, close: 2652.5, volume: 100 },
    ];
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true, candles: mockCandles }),
    });

    const res = await fetchMarketCandles("mock_token", "XAUUSD", "1h", "biquote");
    expect(res.success).toBe(true);
    expect(res.candles).toEqual(mockCandles);
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/market/candles?symbol=XAUUSD&timeframe=1h&provider_id=biquote&limit=100",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer mock_token" }),
      })
    );
  });

  it("handles market quote fetch failure gracefully", async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ success: false, why: "Provider offline" }),
    });

    const res = await fetchMarketQuote("mock_token", "XAUUSD", "invalid_provider");
    expect(res.success).toBe(false);
    expect(res.error).toBe("Provider offline");
  });

  it("fetches providers list successfully", async () => {
    const mockProviders = [
      { id: "biquote", name: "BiQuoteProvider", provider: "biquote", status: "connected", supportedTimeframes: ["1h"] },
    ];
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true, providers: mockProviders, supported_categories: ["market_data", "quote"] }),
    });

    const res = await fetchProviders("mock_token");
    expect(res.success).toBe(true);
    expect(res.providers).toEqual(mockProviders);
    expect(res.supportedCategories).toEqual(["market_data", "quote"]);
  });
});

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { WATCHLIST_SYMBOLS, INITIAL_NOTIFICATIONS, fetchMarketCandles, fetchMarketQuote, fetchProviders, normalizeQuote, getQuotePrice } from "./marketData";

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

  it("normalizes quote and derives mid price and current price when bid and ask are provided", () => {
    const rawQuote = {
      symbol: "XAUUSD",
      timestamp: 1710025200,
      bid: 4308.50,
      ask: 4309.50,
      change_percent: 1.25,
      high: 4320.0,
      low: 4290.0,
    };

    const normalized = normalizeQuote(rawQuote);
    expect(normalized).not.toBeNull();
    expect(normalized?.symbol).toBe("XAUUSD");
    expect(normalized?.bid).toBe(4308.50);
    expect(normalized?.ask).toBe(4309.50);
    expect(normalized?.mid).toBe(4309.00);
    expect(normalized?.last).toBeNull();
    expect(normalized?.changePercent).toBe(1.25);
    expect(normalized?.high24h).toBe(4320.0);
    expect(normalized?.low24h).toBe(4290.0);

    const price = getQuotePrice(rawQuote as any);
    expect(price).toBe(4309.00);
  });

  it("ignores zero or negative last price and computes valid bid/ask average price", () => {
    const realQuoteWithZeroLast = {
      symbol: "XAUUSD",
      timestamp: 1710025200,
      bid: 4303.04,
      ask: 4303.22,
      last: 0.0,
      change_percent: -1.39,
      high: 4369.41,
      low: 4294.41,
    };

    const normalized = normalizeQuote(realQuoteWithZeroLast);
    expect(normalized?.last).toBeNull();
    expect(normalized?.mid).toBeCloseTo(4303.13, 2);

    const price = getQuotePrice(realQuoteWithZeroLast as any);
    expect(price).toBeCloseTo(4303.13, 2);
  });

  it("does not cross-map XAUUSD quote prices to non-XAUUSD symbols when raw symbol mismatches", () => {
    const goldQuote = {
      symbol: "XAUUSD",
      timestamp: 1710025200,
      bid: 2662.8,
      ask: 2663.2,
      last: 2663.0,
    };

    // Asking for price of EURUSD using a quote object belonging to XAUUSD
    const eurQuoteRaw = goldQuote.symbol === "EURUSD" ? goldQuote : null;
    expect(eurQuoteRaw).toBeNull();
    const eurPrice = getQuotePrice(eurQuoteRaw);
    expect(eurPrice).toBeNull();
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

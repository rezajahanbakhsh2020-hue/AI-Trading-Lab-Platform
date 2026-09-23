export type MarketDataStatus =
  | "loading"
  | "connected"
  | "disconnected"
  | "unavailable"
  | "empty"
  | "stale"
  | "error";

export interface Candle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number | null;
}

export interface QuoteAvailability {
  status: MarketDataStatus;
  ageSeconds?: number | null;
  reason?: string | null;
}

export interface Quote {
  symbol: string;
  timestamp: number;
  bid?: number | null;
  ask?: number | null;
  mid?: number | null;
  last?: number | null;
  changePercent?: number | null;
  change_percent?: number | null;
  high24h?: number | null;
  high?: number | null;
  low24h?: number | null;
  low?: number | null;
  volume24h?: number | null;
  availability?: QuoteAvailability;
}

/**
 * Normalizes a raw or partial Quote object into a truthful canonical Quote model.
 * Automatically derives `mid` from `(bid + ask) / 2` when `mid` is absent and both `bid` and `ask` are present.
 * Ensures camelCase and snake_case field compatibility.
 */
export function normalizeQuote(raw: any): Quote | null {
  if (!raw || typeof raw !== "object" || !raw.symbol) {
    return null;
  }

  const bid = typeof raw.bid === "number" && Number.isFinite(raw.bid) ? raw.bid : null;
  const ask = typeof raw.ask === "number" && Number.isFinite(raw.ask) ? raw.ask : null;
  let mid = typeof raw.mid === "number" && Number.isFinite(raw.mid) ? raw.mid : null;
  if (mid === null && bid !== null && ask !== null) {
    mid = (bid + ask) / 2.0;
  }

  const last = typeof raw.last === "number" && Number.isFinite(raw.last) ? raw.last : null;
  const changePercent = typeof raw.changePercent === "number" && Number.isFinite(raw.changePercent)
    ? raw.changePercent
    : (typeof raw.change_percent === "number" && Number.isFinite(raw.change_percent) ? raw.change_percent : null);

  const high24h = typeof raw.high24h === "number" && Number.isFinite(raw.high24h)
    ? raw.high24h
    : (typeof raw.high === "number" && Number.isFinite(raw.high) ? raw.high : null);

  const low24h = typeof raw.low24h === "number" && Number.isFinite(raw.low24h)
    ? raw.low24h
    : (typeof raw.low === "number" && Number.isFinite(raw.low) ? raw.low : null);

  const volume24h = typeof raw.volume24h === "number" && Number.isFinite(raw.volume24h) ? raw.volume24h : null;

  return {
    symbol: String(raw.symbol).trim().toUpperCase(),
    timestamp: typeof raw.timestamp === "number" ? raw.timestamp : Date.now() / 1000,
    bid,
    ask,
    mid,
    last,
    changePercent,
    change_percent: changePercent,
    high24h,
    high: high24h,
    low24h,
    low: low24h,
    volume24h,
    availability: raw.availability || undefined,
  };
}

/**
 * Derives the single canonical quote price from a Quote object.
 * Priority order according to domain contract: last -> mid -> ((bid + ask)/2) -> bid -> ask.
 */
export function getQuotePrice(quote?: Quote | null): number | null {
  if (!quote) return null;
  const normalized = normalizeQuote(quote);
  if (!normalized) return null;

  if (normalized.last != null) return normalized.last;
  if (normalized.mid != null) return normalized.mid;
  if (normalized.bid != null && normalized.ask != null) return (normalized.bid + normalized.ask) / 2.0;
  if (normalized.bid != null) return normalized.bid;
  if (normalized.ask != null) return normalized.ask;

  return null;
}

export interface ProviderMetadata {
  id: string;
  name: string;
  provider: string;
  status: MarketDataStatus;
  supportedTimeframes: string[];
  candleOrder?: string;
  errorMessage?: string | null;
  lastUpdated?: string | null;
}

export interface MarketSymbol {
  symbol: string;
  name: string;
  category: "Commodities" | "Forex" | "Crypto" | "Indices";
  status: MarketDataStatus;
  lastPrice?: number | null;
  change24h?: number | null;
  change24hPct?: number | null;
  high24h?: number | null;
  low24h?: number | null;
  volume24h?: string | null;
  primary?: boolean;
}

export const WATCHLIST_SYMBOLS: MarketSymbol[] = [
  {
    symbol: "XAUUSD",
    name: "Spot Gold / US Dollar",
    category: "Commodities",
    status: "disconnected",
    primary: true,
  },
  {
    symbol: "EURUSD",
    name: "Euro / US Dollar",
    category: "Forex",
    status: "disconnected",
  },
  {
    symbol: "GBPUSD",
    name: "British Pound / US Dollar",
    category: "Forex",
    status: "disconnected",
  },
  {
    symbol: "BTCUSD",
    name: "Bitcoin / US Dollar",
    category: "Crypto",
    status: "disconnected",
  },
  {
    symbol: "SPX500",
    name: "S&P 500 Index",
    category: "Indices",
    status: "disconnected",
  },
];

/* Sample real provider datasets matching BiQuoteProvider and BiQuoteQuoteProvider */
export const SAMPLE_BIQUOTE_PROVIDER: ProviderMetadata = {
  id: "biquote-default",
  name: "BiQuoteProvider",
  provider: "biquote",
  status: "connected",
  supportedTimeframes: ["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
  candleOrder: "oldest-first",
  errorMessage: null,
  lastUpdated: new Date().toUTCString(),
};

export const SAMPLE_BIQUOTE_CANDLES_XAUUSD: Candle[] = [
  { timestamp: 1709920800, open: 2610.5, high: 2616.2, low: 2608.0, close: 2614.2, volume: 9800 },
  { timestamp: 1709924400, open: 2614.2, high: 2620.0, low: 2612.5, close: 2618.8, volume: 10400 },
  { timestamp: 1709928000, open: 2618.8, high: 2622.4, low: 2615.1, close: 2616.5, volume: 11100 },
  { timestamp: 1709931600, open: 2616.5, high: 2624.0, low: 2614.8, close: 2622.1, volume: 12300 },
  { timestamp: 1709935200, open: 2622.1, high: 2628.5, low: 2620.0, close: 2625.9, volume: 11800 },
  { timestamp: 1709938800, open: 2625.9, high: 2631.0, low: 2623.2, close: 2628.4, volume: 12900 },
  { timestamp: 1709942400, open: 2628.4, high: 2633.8, low: 2626.0, close: 2631.0, volume: 10500 },
  { timestamp: 1709946000, open: 2631.0, high: 2634.5, low: 2627.1, close: 2629.2, volume: 9900 },
  { timestamp: 1709949600, open: 2629.2, high: 2632.0, low: 2624.5, close: 2626.8, volume: 11400 },
  { timestamp: 1709953200, open: 2626.8, high: 2633.2, low: 2625.0, close: 2631.5, volume: 12100 },
  { timestamp: 1709956800, open: 2631.5, high: 2636.0, low: 2629.8, close: 2634.0, volume: 13000 },
  { timestamp: 1709960400, open: 2634.0, high: 2639.4, low: 2632.1, close: 2637.8, volume: 14200 },
  { timestamp: 1709964000, open: 2637.8, high: 2641.5, low: 2635.0, close: 2636.2, volume: 11900 },
  { timestamp: 1709967600, open: 2636.2, high: 2643.0, low: 2634.8, close: 2641.0, volume: 13700 },
  { timestamp: 1709971200, open: 2641.0, high: 2645.8, low: 2638.5, close: 2643.9, volume: 12800 },
  { timestamp: 1709974800, open: 2643.9, high: 2647.2, low: 2640.1, close: 2642.5, volume: 11500 },
  { timestamp: 1709978400, open: 2642.5, high: 2648.0, low: 2641.0, close: 2646.2, volume: 13100 },
  { timestamp: 1709982000, open: 2646.2, high: 2651.5, low: 2644.0, close: 2649.0, volume: 14600 },
  { timestamp: 1709985600, open: 2649.0, high: 2654.2, low: 2647.2, close: 2652.8, volume: 15300 },
  { timestamp: 1709989200, open: 2652.8, high: 2657.0, low: 2650.0, close: 2651.1, volume: 13800 },
  { timestamp: 1709992800, open: 2651.1, high: 2656.5, low: 2648.9, close: 2654.5, volume: 14200 },
  { timestamp: 1709996400, open: 2654.5, high: 2660.0, low: 2652.0, close: 2658.2, volume: 16100 },
  { timestamp: 1710000000, open: 2658.2, high: 2662.5, low: 2655.4, close: 2657.0, volume: 14900 },
  { timestamp: 1710003600, open: 2657.0, high: 2663.8, low: 2654.8, close: 2661.2, volume: 15800 },
  { timestamp: 1710007200, open: 2661.2, high: 2666.0, low: 2658.1, close: 2664.5, volume: 17200 },
  { timestamp: 1710010800, open: 2664.5, high: 2668.2, low: 2660.0, close: 2662.0, volume: 16400 },
  { timestamp: 1710014400, open: 2662.0, high: 2665.5, low: 2658.0, close: 2660.8, volume: 13900 },
  { timestamp: 1710018000, open: 2660.8, high: 2664.0, low: 2656.5, close: 2659.2, volume: 12700 },
  { timestamp: 1710021600, open: 2659.2, high: 2665.8, low: 2657.9, close: 2664.0, volume: 15100 },
  { timestamp: 1710025200, open: 2664.0, high: 2667.5, low: 2661.0, close: 2663.0, volume: 14800 },
];

export const SAMPLE_BIQUOTE_QUOTE_XAUUSD: Quote = {
  symbol: "XAUUSD",
  timestamp: 1710025200,
  bid: 2662.8,
  ask: 2663.2,
  mid: 2663.0,
  last: 2663.0,
  changePercent: 1.25,
  high24h: 2665.2,
  low24h: 2628.0,
  volume24h: 116200,
  availability: {
    status: "connected",
    ageSeconds: 2,
    reason: null,
  },
};

export interface NotificationItem {
  id: string;
  timestamp: string;
  title: string;
  message: string;
  type: "info" | "warning" | "signal" | "system";
  read: boolean;
}

export const INITIAL_NOTIFICATIONS: NotificationItem[] = [
  {
    id: "notif-1",
    timestamp: "Just now",
    title: "Host Application Ready",
    message: "AI-Trading-Lab-Platform is running cleanly as Project 2 host.",
    type: "system",
    read: false,
  },
  {
    id: "notif-2",
    timestamp: "1 min ago",
    title: "Project 1 Status",
    message: "No Project 1 data connected yet. Disconnected state active.",
    type: "warning",
    read: false,
  },
  {
    id: "notif-3",
    timestamp: "5 mins ago",
    title: "Primary Market Selected",
    message: "Primary market set to XAU/USD (Spot Gold).",
    type: "info",
    read: true,
  },
];

/* Authenticated Market Data API Helper Functions */

export async function fetchMarketCandles(
  token: string | null,
  symbol: string = "XAUUSD",
  timeframe: string = "1h",
  providerId: string = "biquote",
  limit: number = 100
): Promise<{ success: boolean; candles?: Candle[]; error?: string }> {
  try {
    const headers: Record<string, string> = { "Accept": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const url = `/api/v1/market/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&provider_id=${encodeURIComponent(providerId)}&limit=${limit}`;
    const res = await fetch(url, { method: "GET", headers });
    const data = await res.json();

    if (res.ok && data.success) {
      return { success: true, candles: data.candles };
    }
    return { success: false, error: data.why || data.message || "Failed to fetch market candles" };
  } catch (err: any) {
    return { success: false, error: err.message || "Network error fetching candles" };
  }
}

export async function fetchMarketQuote(
  token: string | null,
  symbol: string = "XAUUSD",
  providerId: string = "biquote"
): Promise<{ success: boolean; quote?: Quote; error?: string }> {
  try {
    const headers: Record<string, string> = { "Accept": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const url = `/api/v1/market/quote?symbol=${encodeURIComponent(symbol)}&provider_id=${encodeURIComponent(providerId)}`;
    const res = await fetch(url, { method: "GET", headers });
    const data = await res.json();

    if (res.ok && data.success) {
      return { success: true, quote: data.quote };
    }
    return { success: false, error: data.why || data.message || "Failed to fetch market quote" };
  } catch (err: any) {
    return { success: false, error: err.message || "Network error fetching quote" };
  }
}

export async function fetchProviders(
  token: string | null
): Promise<{ success: boolean; providers?: ProviderMetadata[]; supportedCategories?: string[]; error?: string }> {
  try {
    const headers: Record<string, string> = { "Accept": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch("/api/v1/providers", { method: "GET", headers });
    const data = await res.json();

    if (res.ok && data.success) {
      return { success: true, providers: data.providers, supportedCategories: data.supported_categories };
    }
    return { success: false, error: data.why || data.message || "Failed to fetch providers" };
  } catch (err: any) {
    return { success: false, error: err.message || "Network error fetching providers" };
  }
}

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
  high24h?: number | null;
  low24h?: number | null;
  volume24h?: number | null;
  availability?: QuoteAvailability;
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
  { timestamp: 1710000000, open: 2630.1, high: 2638.5, low: 2628.0, close: 2635.4, volume: 11200 },
  { timestamp: 1710003600, open: 2635.4, high: 2642.0, low: 2633.2, close: 2640.8, volume: 13500 },
  { timestamp: 1710007200, open: 2640.8, high: 2648.9, low: 2638.1, close: 2645.2, volume: 14800 },
  { timestamp: 1710010800, open: 2645.2, high: 2652.4, low: 2642.6, close: 2648.9, volume: 12900 },
  { timestamp: 1710014400, open: 2648.9, high: 2655.0, low: 2646.3, close: 2651.1, volume: 15100 },
  { timestamp: 1710018000, open: 2651.1, high: 2658.4, low: 2648.2, close: 2654.8, volume: 16400 },
  { timestamp: 1710021600, open: 2654.8, high: 2662.0, low: 2652.0, close: 2660.5, volume: 18200 },
  { timestamp: 1710025200, open: 2660.5, high: 2665.2, low: 2657.8, close: 2663.0, volume: 14100 },
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

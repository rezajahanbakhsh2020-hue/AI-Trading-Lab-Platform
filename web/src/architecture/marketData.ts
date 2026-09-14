export interface MarketSymbol {
  symbol: string;
  name: string;
  category: "Commodities" | "Forex" | "Crypto" | "Indices";
  status: "Connected" | "Disconnected" | "Unavailable";
  lastPrice?: number;
  change24h?: number;
  change24hPct?: number;
  high24h?: number;
  low24h?: number;
  volume24h?: string;
  primary?: boolean;
}

export const WATCHLIST_SYMBOLS: MarketSymbol[] = [
  {
    symbol: "XAUUSD",
    name: "Spot Gold / US Dollar",
    category: "Commodities",
    status: "Disconnected",
    primary: true,
  },
  {
    symbol: "EURUSD",
    name: "Euro / US Dollar",
    category: "Forex",
    status: "Disconnected",
  },
  {
    symbol: "GBPUSD",
    name: "British Pound / US Dollar",
    category: "Forex",
    status: "Disconnected",
  },
  {
    symbol: "BTCUSD",
    name: "Bitcoin / US Dollar",
    category: "Crypto",
    status: "Disconnected",
  },
  {
    symbol: "SPX500",
    name: "S&P 500 Index",
    category: "Indices",
    status: "Disconnected",
  },
];

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

import type { HostSnapshot } from "./hostView";
import { ACADEMY_CATEGORIES, GLOSSARY_ITEMS } from "./academyData";

export type SearchCategory =
  | "navigation"
  | "market"
  | "signal"
  | "watchlist"
  | "strategy"
  | "risk"
  | "health"
  | "provider"
  | "academy"
  | "setting";

export interface CommandItem {
  id: string;
  title: string;
  category: SearchCategory;
  description?: string;
  route: string;
  badge?: string;
  requiresAdmin?: boolean;
  actionSymbol?: string;
}

export interface CommandGroup {
  category: SearchCategory;
  categoryLabelKey: string;
  items: CommandItem[];
}

const RECENT_SEARCHES_KEY = "ai_trading_lab_recent_searches_v1";
const MAX_RECENT = 5;

export function loadRecentSearches(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_SEARCHES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(0, MAX_RECENT) : [];
  } catch {
    return [];
  }
}

export function saveRecentSearch(query: string): string[] {
  const clean = query.trim();
  if (!clean) return loadRecentSearches();
  const existing = loadRecentSearches().filter(
    (item) => item.toLowerCase() !== clean.toLowerCase()
  );
  const updated = [clean, ...existing].slice(0, MAX_RECENT);
  try {
    localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(updated));
  } catch {
    // Ignore storage errors
  }
  return updated;
}

export function clearRecentSearches(): void {
  try {
    localStorage.removeItem(RECENT_SEARCHES_KEY);
  } catch {
    // Ignore storage errors
  }
}

export function queryCommandCenter(
  query: string,
  snapshot: HostSnapshot
): CommandGroup[] {
  const cleanQuery = query.trim().toLowerCase();
  const isAdmin = snapshot.security?.isAdmin ?? false;

  const allItems: CommandItem[] = [];

  // 1. Navigation items
  const navItems: CommandItem[] = [
    { id: "nav-dashboard", title: "Dashboard", category: "navigation", description: "Host overview & operational metrics", route: "/" },
    { id: "nav-markets", title: "Markets & Chart", category: "navigation", description: "Real-time quotes and interactive candles", route: "/markets" },
    { id: "nav-watchlist", title: "Watchlist", category: "navigation", description: "Personal workspace watchlists", route: "/watchlist" },
    { id: "nav-signals", title: "Signals Feed", category: "navigation", description: "Validated Project 1 signal feed", route: "/signals" },
    { id: "nav-strategies", title: "Strategies", category: "navigation", description: "Strategy readiness & stability metrics", route: "/strategies" },
    { id: "nav-backtest", title: "Backtest", category: "navigation", description: "Walk-forward validation assessment", route: "/backtest" },
    { id: "nav-performance", title: "Performance", category: "navigation", description: "Sharpe ratio & win rate metrics", route: "/performance" },
    { id: "nav-risk", title: "Risk Management", category: "navigation", description: "Position sizing & R:R calculator", route: "/risk" },
    { id: "nav-health", title: "Health Center", category: "navigation", description: "Connection health & provider status", route: "/health" },
    { id: "nav-monitoring", title: "Monitoring", category: "navigation", description: "Data freshness & live observer", route: "/monitoring" },
    { id: "nav-providers", title: "Providers", category: "navigation", description: "Registered provider slots", route: "/providers" },
    { id: "nav-academy", title: "Academy & Guides", category: "navigation", description: "Quantitative trading concepts", route: "/academy" },
    { id: "nav-notifications", title: "Notifications Inbox", category: "navigation", description: "System alerts & event stream", route: "/notifications" },
    { id: "nav-settings", title: "Settings", category: "navigation", description: "Platform policy & system guardrails", route: "/settings" },
  ];

  for (const item of navItems) {
    if (
      !cleanQuery ||
      item.title.toLowerCase().includes(cleanQuery) ||
      (item.description && item.description.toLowerCase().includes(cleanQuery))
    ) {
      allItems.push(item);
    }
  }

  // 2. Market symbols
  const staticSymbols = [
    { symbol: "XAUUSD", name: "Gold / US Dollar", cat: "Precious Metals" },
    { symbol: "EURUSD", name: "Euro / US Dollar", cat: "Forex Major" },
    { symbol: "GBPUSD", name: "British Pound / US Dollar", cat: "Forex Major" },
    { symbol: "BTCUSD", name: "Bitcoin / US Dollar", cat: "Crypto Asset" },
    { symbol: "SPX500", name: "S&P 500 Index", cat: "Equity Index" },
  ];

  for (const sym of staticSymbols) {
    if (
      !cleanQuery ||
      sym.symbol.toLowerCase().includes(cleanQuery) ||
      sym.name.toLowerCase().includes(cleanQuery) ||
      sym.cat.toLowerCase().includes(cleanQuery)
    ) {
      allItems.push({
        id: `market-${sym.symbol}`,
        title: sym.symbol,
        category: "market",
        description: `${sym.name} (${sym.cat})`,
        route: `/markets?symbol=${sym.symbol}`,
        actionSymbol: sym.symbol,
        badge: sym.symbol === snapshot.market.symbol ? "ACTIVE" : undefined,
      });
    }
  }

  // 3. Signals
  if (!cleanQuery || cleanQuery.includes("sig") || cleanQuery.includes("buy") || cleanQuery.includes("sell") || cleanQuery.includes("xau")) {
    if (snapshot.signal.action) {
      const confStr = snapshot.signal.confidence != null ? `${(snapshot.signal.confidence * 100).toFixed(0)}%` : "N/A";
      allItems.push({
        id: `signal-${snapshot.signal.signalId || "latest"}`,
        title: `Signal: ${snapshot.signal.action} ${snapshot.market.symbol}`,
        category: "signal",
        description: `Confidence: ${confStr} | Timeframe: ${snapshot.market.timeframe}`,
        route: "/signals",
        badge: snapshot.signal.action,
      });
    }
  }

  // 4. Strategies
  if (!cleanQuery || cleanQuery.includes("strat") || cleanQuery.includes("gold") || cleanQuery.includes("stab")) {
    allItems.push({
      id: "strat-gold-breakout",
      title: "Gold Breakout Momentum Strategy",
      category: "strategy",
      description: "Validated Project 1 momentum strategy",
      route: "/strategies",
      badge: "ACTIVE",
    });
  }

  // Protected Admin-Only Strategy Details (Only visible if isAdmin is true)
  if (isAdmin) {
    if (!cleanQuery || cleanQuery.includes("research") || cleanQuery.includes("admin") || cleanQuery.includes("param")) {
      allItems.push({
        id: "strat-admin-research",
        title: "Admin Strategy Calibrations & Lab Research",
        category: "strategy",
        description: "Protected parameter calibrations & research logs",
        route: "/strategies#admin",
        requiresAdmin: true,
        badge: "ADMIN",
      });
    }
  }

  // 5. Risk
  if (!cleanQuery || cleanQuery.includes("risk") || cleanQuery.includes("sl") || cleanQuery.includes("tp")) {
    allItems.push({
      id: "risk-calc",
      title: "Trade Risk Breakdown",
      category: "risk",
      description: `Entry: ${snapshot.risk.entry ?? "N/A"} | Stop Loss: ${snapshot.risk.stopLoss ?? "N/A"}`,
      route: "/risk",
    });
  }

  // 6. Health & Providers
  if (!cleanQuery || cleanQuery.includes("health") || cleanQuery.includes("status") || cleanQuery.includes("conn")) {
    allItems.push({
      id: "health-center",
      title: "Health & Connection Status",
      category: "health",
      description: `Overall status: ${snapshot.platform.status}`,
      route: "/health",
      badge: snapshot.platform.status.toUpperCase(),
    });
  }

  if (!cleanQuery || cleanQuery.includes("provider") || cleanQuery.includes("quote")) {
    allItems.push({
      id: "provider-biquote",
      title: snapshot.market.provider?.name || "BiQuote Provider",
      category: "provider",
      description: "Market quote & candle provider",
      route: "/providers",
    });
  }

  // 7. Academy & Glossary
  for (const cat of ACADEMY_CATEGORIES) {
    for (const art of cat.articles) {
      if (
        !cleanQuery ||
        art.title.toLowerCase().includes(cleanQuery) ||
        art.summary.toLowerCase().includes(cleanQuery)
      ) {
        allItems.push({
          id: `academy-${art.id}`,
          title: art.title,
          category: "academy",
          description: art.summary,
          route: `/academy?article=${art.id}`,
        });
      }
    }
  }

  for (const item of GLOSSARY_ITEMS) {
    if (
      !cleanQuery ||
      item.term.toLowerCase().includes(cleanQuery) ||
      item.definition.toLowerCase().includes(cleanQuery)
    ) {
      allItems.push({
        id: `glossary-${item.term.toLowerCase().replace(/[^a-z0-9]/g, "-")}`,
        title: `Glossary: ${item.term}`,
        category: "academy",
        description: item.definition,
        route: "/academy#glossary",
      });
    }
  }

  // Group items by category
  const groupsMap = new Map<SearchCategory, CommandItem[]>();
  for (const item of allItems) {
    const existing = groupsMap.get(item.category) || [];
    groupsMap.set(item.category, [...existing, item]);
  }

  const categoryOrder: SearchCategory[] = [
    "navigation",
    "market",
    "signal",
    "watchlist",
    "strategy",
    "risk",
    "health",
    "provider",
    "academy",
    "setting",
  ];

  const resultGroups: CommandGroup[] = [];
  for (const cat of categoryOrder) {
    const items = groupsMap.get(cat);
    if (items && items.length > 0) {
      resultGroups.push({
        category: cat,
        categoryLabelKey: `nav.${cat === "market" ? "markets" : cat === "setting" ? "settings" : cat}`,
        items: items.slice(0, 8),
      });
    }
  }

  return resultGroups;
}

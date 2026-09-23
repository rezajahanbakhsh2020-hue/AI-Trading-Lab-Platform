import { WATCHLIST_SYMBOLS, type MarketSymbol, type Quote, type MarketDataStatus } from "./marketData";

export interface Watchlist {
  id: string;
  name: string;
  symbols: string[];
  isDefault?: boolean;
}

export interface Workspace {
  userId: string;
  activeWatchlistId: string;
  activeSymbol: string;
  watchlists: Record<string, Watchlist>;
  chartPreferences: {
    timeframe: string;
    chartType: string;
  };
  layoutPreferences: {
    selectedPanels: string[];
    dashboardLayout: string;
  };
}

export const KNOWN_MARKET_SYMBOLS: Record<string, Partial<MarketSymbol>> = {
  XAUUSD: { name: "Spot Gold / US Dollar", category: "Commodities" },
  EURUSD: { name: "Euro / US Dollar", category: "Forex" },
  GBPUSD: { name: "British Pound / US Dollar", category: "Forex" },
  BTCUSD: { name: "Bitcoin / US Dollar", category: "Crypto" },
  ETHUSD: { name: "Ethereum / US Dollar", category: "Crypto" },
  SPX500: { name: "S&P 500 Index", category: "Indices" },
  NAS100: { name: "Nasdaq 100 Index", category: "Indices" },
  USOIL: { name: "Crude Oil WTI", category: "Commodities" },
};

export const DEFAULT_WORKSPACE: Workspace = {
  userId: "user_default",
  activeWatchlistId: "default",
  activeSymbol: "XAUUSD",
  watchlists: {
    default: {
      id: "default",
      name: "Main Watchlist",
      symbols: ["XAUUSD", "EURUSD", "GBPUSD", "BTCUSD", "SPX500"],
      isDefault: true,
    },
    forex: {
      id: "forex",
      name: "Forex Majors",
      symbols: ["EURUSD", "GBPUSD"],
      isDefault: false,
    },
    crypto: {
      id: "crypto",
      name: "Crypto Assets",
      symbols: ["BTCUSD", "ETHUSD"],
      isDefault: false,
    },
  },
  chartPreferences: {
    timeframe: "1h",
    chartType: "candlestick",
  },
  layoutPreferences: {
    selectedPanels: ["chart", "watchlist", "signal"],
    dashboardLayout: "default",
  },
};

const STORAGE_KEY_PREFIX = "ai_trading_lab_workspace_";

export function getStorageKey(userId: string = "user_default"): string {
  return `${STORAGE_KEY_PREFIX}${userId}`;
}

export function loadUserWorkspace(userId: string = "user_default"): Workspace {
  try {
    const raw = localStorage.getItem(getStorageKey(userId));
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && parsed.watchlists && parsed.activeWatchlistId) {
        return {
          ...DEFAULT_WORKSPACE,
          ...parsed,
          userId,
        };
      }
    }
  } catch {
    // Fall back to DEFAULT_WORKSPACE on localStorage error or SSR environment
  }
  return { ...DEFAULT_WORKSPACE, userId };
}

export function saveUserWorkspace(workspace: Workspace): void {
  try {
    localStorage.setItem(getStorageKey(workspace.userId), JSON.stringify(workspace));
  } catch {
    // Ignore storage quota/security errors
  }
}

export function addSymbolToWatchlist(
  workspace: Workspace,
  watchlistId: string,
  symbol: string
): Workspace {
  const norm = symbol.trim().toUpperCase();
  if (!norm) return workspace;

  const wl = workspace.watchlists[watchlistId];
  if (!wl) return workspace;

  if (wl.symbols.includes(norm)) return workspace;

  const updatedWl = {
    ...wl,
    symbols: [...wl.symbols, norm],
  };

  const updated: Workspace = {
    ...workspace,
    watchlists: {
      ...workspace.watchlists,
      [watchlistId]: updatedWl,
    },
  };
  saveUserWorkspace(updated);
  return updated;
}

export function removeSymbolFromWatchlist(
  workspace: Workspace,
  watchlistId: string,
  symbol: string
): Workspace {
  const norm = symbol.trim().toUpperCase();
  const wl = workspace.watchlists[watchlistId];
  if (!wl) return workspace;

  const updatedWl = {
    ...wl,
    symbols: wl.symbols.filter((s) => s !== norm),
  };

  const updated: Workspace = {
    ...workspace,
    watchlists: {
      ...workspace.watchlists,
      [watchlistId]: updatedWl,
    },
  };
  saveUserWorkspace(updated);
  return updated;
}

export function createWatchlistInWorkspace(
  workspace: Workspace,
  name: string,
  initialSymbols: string[] = []
): Workspace {
  const cleanName = name.trim();
  if (!cleanName) return workspace;

  const newId = `wl_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
  const cleanSymbols = Array.from(
    new Set(initialSymbols.map((s) => s.trim().toUpperCase()).filter(Boolean))
  );

  const newWl: Watchlist = {
    id: newId,
    name: cleanName,
    symbols: cleanSymbols.length > 0 ? cleanSymbols : ["XAUUSD"],
    isDefault: false,
  };

  const updated: Workspace = {
    ...workspace,
    activeWatchlistId: newId,
    watchlists: {
      ...workspace.watchlists,
      [newId]: newWl,
    },
  };
  saveUserWorkspace(updated);
  return updated;
}

export function renameWatchlistInWorkspace(
  workspace: Workspace,
  watchlistId: string,
  newName: string
): Workspace {
  const cleanName = newName.trim();
  const wl = workspace.watchlists[watchlistId];
  if (!cleanName || !wl || wl.name === cleanName) return workspace;

  const updatedWl = { ...wl, name: cleanName };
  const updated: Workspace = {
    ...workspace,
    watchlists: {
      ...workspace.watchlists,
      [watchlistId]: updatedWl,
    },
  };
  saveUserWorkspace(updated);
  return updated;
}

export function deleteWatchlistFromWorkspace(
  workspace: Workspace,
  watchlistId: string
): Workspace {
  if (Object.keys(workspace.watchlists).length <= 1) {
    return workspace;
  }
  if (!workspace.watchlists[watchlistId]) {
    return workspace;
  }

  const newWatchlists = { ...workspace.watchlists };
  delete newWatchlists[watchlistId];

  const newActiveId =
    workspace.activeWatchlistId === watchlistId
      ? Object.keys(newWatchlists)[0]
      : workspace.activeWatchlistId;

  const updated: Workspace = {
    ...workspace,
    activeWatchlistId: newActiveId,
    watchlists: newWatchlists,
  };
  saveUserWorkspace(updated);
  return updated;
}

export type SortField = "symbol" | "name" | "price" | "change";
export type SortDirection = "asc" | "desc";

export interface WatchlistSymbolRow extends MarketSymbol {
  quote?: Quote | null;
}

export function mapWatchlistSymbols(
  symbols: string[],
  activeQuote?: Quote | null,
  marketStatus: MarketDataStatus = "disconnected"
): WatchlistSymbolRow[] {
  return symbols.map((sym) => {
    const known = KNOWN_MARKET_SYMBOLS[sym] || {};
    const baseSym = WATCHLIST_SYMBOLS.find((s) => s.symbol === sym);

    const isMatch = activeQuote && activeQuote.symbol === sym;
    const rawStatus = isMatch
      ? (activeQuote.availability?.status || marketStatus)
      : "disconnected";
    const currentStatus: MarketDataStatus = rawStatus === "live" ? "connected" : (rawStatus as MarketDataStatus);

    const lastPrice = isMatch
      ? (activeQuote.last ?? activeQuote.mid ?? activeQuote.bid ?? null)
      : (baseSym?.lastPrice ?? null);

    const change24hPct = isMatch
      ? (activeQuote.changePercent ?? null)
      : (baseSym?.change24hPct ?? null);

    return {
      symbol: sym,
      name: known.name || baseSym?.name || `${sym} Asset`,
      category: (known.category || baseSym?.category || "Commodities") as any,
      status: currentStatus,
      lastPrice,
      change24hPct,
      high24h: isMatch ? activeQuote.high24h ?? null : baseSym?.high24h ?? null,
      low24h: isMatch ? activeQuote.low24h ?? null : baseSym?.low24h ?? null,
      volume24h: isMatch && activeQuote.volume24h ? activeQuote.volume24h.toLocaleString() : (baseSym?.volume24h ?? null),
      quote: isMatch ? activeQuote : null,
      primary: sym === "XAUUSD",
    };
  });
}

export function filterAndSortWatchlistRows(
  rows: WatchlistSymbolRow[],
  category: string,
  searchQuery: string,
  sortField: SortField = "symbol",
  sortDirection: SortDirection = "asc"
): WatchlistSymbolRow[] {
  const query = searchQuery.trim().toLowerCase();

  const filtered = rows.filter((row) => {
    const matchesCategory = category === "All" || row.category === category;
    const matchesQuery =
      !query ||
      row.symbol.toLowerCase().includes(query) ||
      row.name.toLowerCase().includes(query);
    return matchesCategory && matchesQuery;
  });

  return filtered.sort((a, b) => {
    let cmp = 0;
    if (sortField === "symbol") {
      cmp = a.symbol.localeCompare(b.symbol);
    } else if (sortField === "name") {
      cmp = a.name.localeCompare(b.name);
    } else if (sortField === "price") {
      const pA = a.lastPrice ?? -Infinity;
      const pB = b.lastPrice ?? -Infinity;
      cmp = pA - pB;
    } else if (sortField === "change") {
      const cA = a.change24hPct ?? -Infinity;
      const cB = b.change24hPct ?? -Infinity;
      cmp = cA - cB;
    }
    return sortDirection === "asc" ? cmp : -cmp;
  });
}

import { describe, it, expect, beforeEach } from "vitest";
import {
  DEFAULT_WORKSPACE,
  addSymbolToWatchlist,
  removeSymbolFromWatchlist,
  createWatchlistInWorkspace,
  renameWatchlistInWorkspace,
  deleteWatchlistFromWorkspace,
  mapWatchlistSymbols,
  filterAndSortWatchlistRows,
  type Workspace,
} from "./workspace";
import type { Quote } from "./marketData";

describe("Frontend Workspace Architecture & Watchlist State", () => {
  let ws: Workspace;

  beforeEach(() => {
    ws = JSON.parse(JSON.stringify(DEFAULT_WORKSPACE));
  });

  it("adds symbol to watchlist without duplicates", () => {
    const updated = addSymbolToWatchlist(ws, "default", "ETHUSD");
    expect(updated.watchlists["default"].symbols).toContain("ETHUSD");

    // Duplicate addition
    const duplicate = addSymbolToWatchlist(updated, "default", "ETHUSD");
    expect(duplicate.watchlists["default"].symbols.filter((s) => s === "ETHUSD")).toHaveLength(1);
  });

  it("removes symbol from watchlist", () => {
    const updated = removeSymbolFromWatchlist(ws, "default", "EURUSD");
    expect(updated.watchlists["default"].symbols).not.toContain("EURUSD");
    expect(updated.watchlists["default"].symbols).toContain("XAUUSD");
  });

  it("creates a new named watchlist and switches activeWatchlistId", () => {
    const updated = createWatchlistInWorkspace(ws, "Tech Indices", ["NAS100", "SPX500"]);
    const activeId = updated.activeWatchlistId;
    expect(updated.watchlists[activeId].name).toBe("Tech Indices");
    expect(updated.watchlists[activeId].symbols).toEqual(["NAS100", "SPX500"]);
  });

  it("renames an existing watchlist", () => {
    const updated = renameWatchlistInWorkspace(ws, "default", "Core Watchlist");
    expect(updated.watchlists["default"].name).toBe("Core Watchlist");
  });

  it("deletes a watchlist and reassigns activeWatchlistId if necessary", () => {
    const created = createWatchlistInWorkspace(ws, "Temp List", ["BTCUSD"]);
    const tempId = created.activeWatchlistId;
    expect(created.watchlists[tempId]).toBeDefined();

    const deleted = deleteWatchlistFromWorkspace(created, tempId);
    expect(deleted.watchlists[tempId]).toBeUndefined();
    expect(deleted.activeWatchlistId).toBe("default");
  });

  it("prevents deleting the last remaining watchlist", () => {
    const singleWs: Workspace = {
      ...ws,
      watchlists: {
        only_one: { id: "only_one", name: "Only One", symbols: ["XAUUSD"] },
      },
      activeWatchlistId: "only_one",
    };

    const attempt = deleteWatchlistFromWorkspace(singleWs, "only_one");
    expect(Object.keys(attempt.watchlists)).toHaveLength(1);
  });

  it("maps watchlist symbols to quote data and handles status correctly", () => {
    const quote: Quote = {
      symbol: "XAUUSD",
      timestamp: 1710000000,
      last: 2665.5,
      changePercent: 1.4,
      availability: { status: "connected" },
    };

    const rows = mapWatchlistSymbols(["XAUUSD", "EURUSD"], quote, "connected");
    expect(rows[0].symbol).toBe("XAUUSD");
    expect(rows[0].lastPrice).toBe(2665.5);
    expect(rows[0].status).toBe("connected");

    expect(rows[1].symbol).toBe("EURUSD");
    expect(rows[1].status).toBe("disconnected");
  });

  it("filters and sorts watchlist rows accurately", () => {
    const rows = mapWatchlistSymbols(["XAUUSD", "EURUSD", "BTCUSD"], null, "disconnected");

    // Filter by category
    const cryptoRows = filterAndSortWatchlistRows(rows, "Crypto", "");
    expect(cryptoRows).toHaveLength(1);
    expect(cryptoRows[0].symbol).toBe("BTCUSD");

    // Sort by symbol desc
    const sortedDesc = filterAndSortWatchlistRows(rows, "All", "", "symbol", "desc");
    expect(sortedDesc[0].symbol).toBe("XAUUSD");
    expect(sortedDesc[1].symbol).toBe("GBPUSD" in sortedDesc ? "GBPUSD" : "EURUSD");
  });
});

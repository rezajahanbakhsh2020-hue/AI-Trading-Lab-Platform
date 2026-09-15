import { useState } from "react";
import { WATCHLIST_SYMBOLS, type MarketSymbol, type Quote } from "../../architecture/marketData";
import { useI18n } from "../../i18n";

type WatchlistWidgetProps = {
  quote?: Quote | null;
  onSelectSymbol?: (symbol: string) => void;
};

export function WatchlistWidget({ quote, onSelectSymbol }: WatchlistWidgetProps) {
  const { t, formatCurrency, formatPercent } = useI18n();
  const [selectedCategory, setSelectedCategory] = useState<string>("All");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const categories = ["All", "Commodities", "Forex", "Crypto", "Indices"];

  const symbolsList: MarketSymbol[] = WATCHLIST_SYMBOLS.map((sym) => {
    if (quote && sym.symbol === quote.symbol) {
      return {
        ...sym,
        status: quote.availability?.status || "connected",
        lastPrice: quote.last ?? quote.mid ?? quote.bid ?? null,
        change24hPct: quote.changePercent ?? null,
        high24h: quote.high24h ?? null,
        low24h: quote.low24h ?? null,
        volume24h: quote.volume24h ? quote.volume24h.toLocaleString() : null,
      };
    }
    return sym;
  });

  const filteredSymbols = symbolsList.filter((item) => {
    const matchesCategory =
      selectedCategory === "All" || item.category === selectedCategory;
    const matchesQuery =
      item.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesQuery;
  });

  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3>{t("watchlist.title")}</h3>
          <p className="hint">{t("watchlist.summary")}</p>
        </div>
        <span className="chip market-chip">{symbolsList.length} Assets</span>
      </div>

      <div className="card-body">
        <div className="watchlist-toolbar">
          <input
            type="text"
            className="input-search"
            placeholder={t("watchlist.searchPlaceholder")}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />

          <div className="category-pills">
            {categories.map((cat) => (
              <button
                key={cat}
                className={
                  selectedCategory === cat ? "pill-btn active" : "pill-btn"
                }
                onClick={() => setSelectedCategory(cat)}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        <div className="table-responsive">
          <table className="table">
            <thead>
              <tr>
                <th>{t("watchlist.columns.symbol")}</th>
                <th>{t("watchlist.columns.marketName")}</th>
                <th>{t("watchlist.columns.category")}</th>
                <th>{t("watchlist.columns.lastPrice")}</th>
                <th>{t("watchlist.columns.change24h")}</th>
                <th>{t("watchlist.columns.status")}</th>
              </tr>
            </thead>
            <tbody>
              {filteredSymbols.map((item) => {
                const isConnected = item.status === "connected";
                const isStale = item.status === "stale";
                const priceText =
                  item.lastPrice != null ? formatCurrency(item.lastPrice) : t("status.unavailable");
                const changeText =
                  item.change24hPct != null ? formatPercent(item.change24hPct) : "—";

                const statusClass =
                  item.status === "connected"
                    ? "ready"
                    : item.status === "stale"
                    ? "warn"
                    : "disconnected";

                return (
                  <tr
                    key={item.symbol}
                    style={{ cursor: onSelectSymbol ? "pointer" : "default" }}
                    onClick={() => onSelectSymbol && onSelectSymbol(item.symbol)}
                  >
                    <td>
                      <div className="symbol-cell">
                        <strong>{item.symbol}</strong>
                        {item.primary && <span className="tag-primary">{t("watchlist.primaryTag")}</span>}
                      </div>
                    </td>
                    <td>{item.name}</td>
                    <td>
                      <span className="badge-soft">{item.category}</span>
                    </td>
                    <td>
                      <span className={isConnected || isStale ? "mono-bold" : "mono-muted"}>
                        {priceText}
                      </span>
                    </td>
                    <td>
                      <span
                        className={
                          item.change24hPct != null && item.change24hPct > 0
                            ? "text-green"
                            : item.change24hPct != null && item.change24hPct < 0
                            ? "text-red"
                            : "mono-muted"
                        }
                      >
                        {changeText}
                      </span>
                    </td>
                    <td>
                      <span className={`status ${statusClass}`}>
                        {item.status === "connected" ? t("status.connected") : item.status === "stale" ? t("status.stale") : t("status.disconnected")}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

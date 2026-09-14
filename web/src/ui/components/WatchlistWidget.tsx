import { useState } from "react";
import { WATCHLIST_SYMBOLS } from "../../architecture/marketData";

export function WatchlistWidget() {
  const [selectedCategory, setSelectedCategory] = useState<string>("All");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const categories = ["All", "Commodities", "Forex", "Crypto", "Indices"];

  const filteredSymbols = WATCHLIST_SYMBOLS.filter((item) => {
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
          <h3>Market Watchlist</h3>
          <p className="hint">Track primary assets across market categories.</p>
        </div>
        <span className="chip market-chip">5 Assets</span>
      </div>

      <div className="card-body">
        <div className="watchlist-toolbar">
          <input
            type="text"
            className="input-search"
            placeholder="Search watchlist symbols..."
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
                <th>Symbol</th>
                <th>Asset Name</th>
                <th>Category</th>
                <th>Price</th>
                <th>Change (24h)</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredSymbols.map((item) => (
                <tr key={item.symbol}>
                  <td>
                    <div className="symbol-cell">
                      <strong>{item.symbol}</strong>
                      {item.primary && <span className="tag-primary">Primary</span>}
                    </div>
                  </td>
                  <td>{item.name}</td>
                  <td>
                    <span className="badge-soft">{item.category}</span>
                  </td>
                  <td>
                    <span className="mono-muted">
                      {item.lastPrice != null ? `$${item.lastPrice}` : "Unavailable"}
                    </span>
                  </td>
                  <td>
                    <span className="mono-muted">
                      {item.change24hPct != null
                        ? `${item.change24hPct > 0 ? "+" : ""}${item.change24hPct}%`
                        : "—"}
                    </span>
                  </td>
                  <td>
                    <span className="status disconnected">{item.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

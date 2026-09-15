import { useState, useMemo } from "react";
import type { Quote, ProviderMetadata } from "../../architecture/marketData";
import {
  loadUserWorkspace,
  addSymbolToWatchlist,
  removeSymbolFromWatchlist,
  createWatchlistInWorkspace,
  renameWatchlistInWorkspace,
  deleteWatchlistFromWorkspace,
  mapWatchlistSymbols,
  filterAndSortWatchlistRows,
  type Workspace,
  type SortField,
  type SortDirection,
} from "../../architecture/workspace";
import { useI18n } from "../../i18n";

type WatchlistWidgetProps = {
  quote?: Quote | null;
  provider?: ProviderMetadata | null;
  userId?: string;
  activeSymbol?: string;
  onSelectSymbol?: (symbol: string) => void;
};

export function WatchlistWidget({
  quote,
  provider,
  userId = "user_default",
  activeSymbol = "XAUUSD",
  onSelectSymbol,
}: WatchlistWidgetProps) {
  const { t, formatCurrency, formatPercent } = useI18n();

  // Load user workspace state
  const [workspace, setWorkspace] = useState<Workspace>(() => loadUserWorkspace(userId));
  const [selectedCategory, setSelectedCategory] = useState<string>("All");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [newSymbolInput, setNewSymbolInput] = useState<string>("");
  const [isCreatingModalOpen, setIsCreatingModalOpen] = useState<boolean>(false);
  const [newWatchlistName, setNewWatchlistName] = useState<string>("");
  const [editingWatchlistId, setEditingWatchlistId] = useState<string | null>(null);
  const [editingWatchlistName, setEditingWatchlistName] = useState<string>("");

  // Sorting state
  const [sortField, setSortField] = useState<SortField>("symbol");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const activeWlId = workspace.activeWatchlistId && workspace.watchlists[workspace.activeWatchlistId]
    ? workspace.activeWatchlistId
    : Object.keys(workspace.watchlists)[0] || "default";

  const currentWatchlist = workspace.watchlists[activeWlId];
  const categories = ["All", "Commodities", "Forex", "Crypto", "Indices"];

  // Map symbols in current active watchlist to data rows
  const mappedRows = useMemo(() => {
    const syms = currentWatchlist ? currentWatchlist.symbols : [];
    const providerStatus = provider ? provider.status : "disconnected";
    return mapWatchlistSymbols(syms, quote, providerStatus);
  }, [currentWatchlist, quote, provider]);

  // Filter and sort rows
  const filteredRows = useMemo(() => {
    return filterAndSortWatchlistRows(
      mappedRows,
      selectedCategory,
      searchQuery,
      sortField,
      sortDirection
    );
  }, [mappedRows, selectedCategory, searchQuery, sortField, sortDirection]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  };

  const handleSelectWatchlist = (id: string) => {
    const updated = { ...workspace, activeWatchlistId: id };
    setWorkspace(updated);
  };

  const handleAddSymbol = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSymbolInput.trim()) return;
    const updated = addSymbolToWatchlist(workspace, activeWlId, newSymbolInput.trim());
    setWorkspace(updated);
    setNewSymbolInput("");
  };

  const handleRemoveSymbol = (symbol: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updated = removeSymbolFromWatchlist(workspace, activeWlId, symbol);
    setWorkspace(updated);
  };

  const handleCreateWatchlist = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWatchlistName.trim()) return;
    const updated = createWatchlistInWorkspace(workspace, newWatchlistName.trim());
    setWorkspace(updated);
    setNewWatchlistName("");
    setIsCreatingModalOpen(false);
  };

  const handleSaveRename = (wlId: string) => {
    if (!editingWatchlistName.trim()) {
      setEditingWatchlistId(null);
      return;
    }
    const updated = renameWatchlistInWorkspace(workspace, wlId, editingWatchlistName.trim());
    setWorkspace(updated);
    setEditingWatchlistId(null);
  };

  const handleDeleteWatchlist = (wlId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updated = deleteWatchlistFromWorkspace(workspace, wlId);
    setWorkspace(updated);
  };

  const providerName = provider ? provider.name : "BiQuoteProvider";
  const freshnessText = quote?.availability?.ageSeconds != null
    ? `${quote.availability.ageSeconds}s ago`
    : quote ? "fresh" : "disconnected";

  return (
    <div className="card watchlist-card-wrapper">
      <div className="card-head">
        <div>
          <h3>{t("watchlist.title")}</h3>
          <p className="hint">{t("watchlist.summary")}</p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button
            className="btn btn-secondary"
            onClick={() => setIsCreatingModalOpen(true)}
            style={{ fontSize: 12, padding: "5px 10px" }}
          >
            {t("buttons.createWatchlist")}
          </button>
          <span className="chip market-chip">
            {mappedRows.length} Assets
          </span>
        </div>
      </div>

      <div className="card-body">
        {/* Watchlist Tabs Bar */}
        <div className="watchlist-tabs-bar">
          {Object.values(workspace.watchlists).map((wl) => {
            const isActive = wl.id === activeWlId;
            const isEditing = editingWatchlistId === wl.id;

            return (
              <div
                key={wl.id}
                className={`watchlist-tab ${isActive ? "active" : ""}`}
                onClick={() => handleSelectWatchlist(wl.id)}
              >
                {isEditing ? (
                  <input
                    type="text"
                    className="input-inline-rename"
                    value={editingWatchlistName}
                    onChange={(e) => setEditingWatchlistName(e.target.value)}
                    onBlur={() => handleSaveRename(wl.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleSaveRename(wl.id);
                    }}
                    autoFocus
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <span className="tab-title">{wl.name}</span>
                )}

                <span className="tab-count">({wl.symbols.length})</span>

                {isActive && !isEditing && (
                  <div className="tab-actions">
                    <button
                      className="tab-action-btn"
                      title={t("buttons.rename")}
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingWatchlistId(wl.id);
                        setEditingWatchlistName(wl.name);
                      }}
                    >
                      ✎
                    </button>

                    {Object.keys(workspace.watchlists).length > 1 && (
                      <button
                        className="tab-action-btn danger"
                        title={t("buttons.delete")}
                        onClick={(e) => handleDeleteWatchlist(wl.id, e)}
                      >
                        ✕
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Search & Toolbar */}
        <div className="watchlist-toolbar">
          <div className="toolbar-search-add">
            <input
              type="text"
              className="input-search"
              placeholder={t("watchlist.searchPlaceholder")}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />

            <form onSubmit={handleAddSymbol} className="add-symbol-form">
              <input
                type="text"
                className="input-add-symbol"
                placeholder={t("watchlist.addSymbolPlaceholder")}
                value={newSymbolInput}
                onChange={(e) => setNewSymbolInput(e.target.value)}
              />
              <button type="submit" className="btn btn-primary btn-add-sm">
                {t("buttons.addSymbol")}
              </button>
            </form>
          </div>

          <div className="category-pills">
            {categories.map((cat) => (
              <button
                key={cat}
                className={selectedCategory === cat ? "pill-btn active" : "pill-btn"}
                onClick={() => setSelectedCategory(cat)}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Data Provider & Freshness Indicator Banner */}
        <div className="provider-freshness-bar hint">
          {t("watchlist.providerInfo", {
            provider: providerName,
            freshness: freshnessText,
          })}
        </div>

        {/* Symbol Table */}
        <div className="table-responsive">
          <table className="table watchlist-table">
            <thead>
              <tr>
                <th onClick={() => handleSort("symbol")} style={{ cursor: "pointer" }}>
                  {t("watchlist.columns.symbol")}{" "}
                  {sortField === "symbol" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                </th>
                <th onClick={() => handleSort("name")} style={{ cursor: "pointer" }}>
                  {t("watchlist.columns.marketName")}{" "}
                  {sortField === "name" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                </th>
                <th>{t("watchlist.columns.category")}</th>
                <th onClick={() => handleSort("price")} style={{ cursor: "pointer" }}>
                  {t("watchlist.columns.lastPrice")}{" "}
                  {sortField === "price" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                </th>
                <th onClick={() => handleSort("change")} style={{ cursor: "pointer" }}>
                  {t("watchlist.columns.change24h")}{" "}
                  {sortField === "change" ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                </th>
                <th>{t("watchlist.columns.status")}</th>
                <th style={{ textAlign: "right" }}>{t("watchlist.columns.action")}</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", padding: "24px 12px" }}>
                    <p className="hint">
                      {mappedRows.length === 0
                        ? t("watchlist.emptyWatchlist")
                        : t("watchlist.emptySearch")}
                    </p>
                  </td>
                </tr>
              ) : (
                filteredRows.map((item) => {
                  const isSelectedSymbol = item.symbol === activeSymbol;
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
                      className={`watchlist-row ${isSelectedSymbol ? "selected-row" : ""}`}
                      onClick={() => onSelectSymbol && onSelectSymbol(item.symbol)}
                      style={{ cursor: "pointer" }}
                    >
                      <td>
                        <div className="symbol-cell">
                          <strong>{item.symbol}</strong>
                          {item.primary && (
                            <span className="tag-primary">{t("watchlist.primaryTag")}</span>
                          )}
                          {isSelectedSymbol && (
                            <span className="tag-active">{t("watchlist.activeTag")}</span>
                          )}
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
                          {item.status === "connected"
                            ? t("status.connected")
                            : item.status === "stale"
                            ? t("status.stale")
                            : t("status.disconnected")}
                        </span>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <button
                          className="btn-icon-remove"
                          title="Remove symbol"
                          onClick={(e) => handleRemoveSymbol(item.symbol, e)}
                        >
                          ✕
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Watchlist Modal */}
      {isCreatingModalOpen && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <h3>{t("watchlist.createModalTitle")}</h3>
            <form onSubmit={handleCreateWatchlist} style={{ marginTop: 12 }}>
              <input
                type="text"
                className="input-modal"
                placeholder={t("watchlist.watchlistNamePlaceholder")}
                value={newWatchlistName}
                onChange={(e) => setNewWatchlistName(e.target.value)}
                autoFocus
              />
              <div className="modal-actions" style={{ marginTop: 16 }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsCreatingModalOpen(false)}
                >
                  {t("buttons.cancel")}
                </button>
                <button type="submit" className="btn btn-primary">
                  {t("buttons.save")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

import React, { useEffect, useState } from 'react';
import {
  AssetCategory,
  MarketScreenerItem,
  filterScreenerItems,
  generateHeatmapTiles,
  fetchMarketScreener,
} from '../../architecture/screener';
import { MarketHeatmap } from './MarketHeatmap';

interface MarketScreenerProps {
  onSelectSymbol?: (symbol: string) => void;
  selectedSymbol?: string;
  itemsOverride?: MarketScreenerItem[];
}

export const MarketScreener: React.FC<MarketScreenerProps> = ({
  onSelectSymbol,
  selectedSymbol,
  itemsOverride,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<AssetCategory>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [signalFilter, setSignalFilter] = useState('ALL');
  const [viewMode, setViewMode] = useState<'list' | 'heatmap'>('heatmap');
  const [items, setItems] = useState<MarketScreenerItem[]>(itemsOverride || []);
  const [isLoading, setIsLoading] = useState(!itemsOverride);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (itemsOverride) {
      setItems(itemsOverride);
      setIsLoading(false);
      return;
    }

    let isSubscribed = true;
    async function loadScreenerData() {
      setIsLoading(true);
      setErrorMsg(null);
      const res = await fetchMarketScreener(null, selectedCategory, searchQuery, signalFilter);
      if (!isSubscribed) return;

      if (res.success && res.data) {
        setItems(res.data.items);
      } else {
        setErrorMsg(res.message || 'Failed to fetch runtime screener dataset.');
      }
      setIsLoading(false);
    }

    loadScreenerData();
    return () => {
      isSubscribed = false;
    };
  }, [itemsOverride, selectedCategory, searchQuery, signalFilter]);

  const filteredItems = itemsOverride
    ? filterScreenerItems(items, selectedCategory, searchQuery, signalFilter)
    : items;

  const heatmapTiles = generateHeatmapTiles(filteredItems);

  const categories: { label: string; value: AssetCategory }[] = [
    { label: 'All Assets', value: 'ALL' },
    { label: 'Commodities', value: 'COMMODITIES' },
    { label: 'Forex', value: 'FOREX' },
    { label: 'Crypto', value: 'CRYPTO' },
    { label: 'Indices', value: 'INDICES' },
  ];

  return (
    <div className="space-y-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800">
      {/* Top Filter Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {categories.map((cat) => (
            <button
              key={cat.value}
              onClick={() => setSelectedCategory(cat.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
                selectedCategory === cat.value
                  ? 'bg-amber-500 text-slate-950 font-bold shadow-md'
                  : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700/80'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search assets (XAU, BTC, Forex..)"
            className="bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-amber-500/50 w-full sm:w-48"
          />

          <select
            value={signalFilter}
            onChange={(e) => setSignalFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-amber-500/50 cursor-pointer"
          >
            <option value="ALL">All Signals</option>
            <option value="BUY">BUY Only</option>
            <option value="SELL">SELL Only</option>
            <option value="NO SIGNAL">NO SIGNAL Only</option>
          </select>

          <div className="flex items-center bg-slate-950 p-1 rounded-lg border border-slate-800">
            <button
              onClick={() => setViewMode('list')}
              className={`px-2.5 py-1 rounded text-xs font-medium cursor-pointer ${
                viewMode === 'list'
                  ? 'bg-slate-800 text-amber-400 font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              📋 List View
            </button>
            <button
              onClick={() => setViewMode('heatmap')}
              className={`px-2.5 py-1 rounded text-xs font-medium cursor-pointer ${
                viewMode === 'heatmap'
                  ? 'bg-slate-800 text-amber-400 font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              🔥 Heatmap View
            </button>
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="text-center py-6 text-xs text-slate-400 animate-pulse">
          Loading market screener runtime dataset...
        </div>
      )}

      {errorMsg && (
        <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-xs text-rose-300">
          {errorMsg}
        </div>
      )}

      {/* Main Content Area */}
      {!isLoading && (
        viewMode === 'heatmap' ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs text-slate-400 px-1">
              <span className="font-semibold text-slate-300">24h Market Performance Heatmap</span>
              <span>{filteredItems.length} Assets</span>
            </div>
            <MarketHeatmap
              tiles={heatmapTiles}
              onSelectSymbol={onSelectSymbol}
              selectedSymbol={selectedSymbol}
            />
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950">
            <table className="w-full text-start text-xs text-slate-300">
              <thead className="bg-slate-900/80 text-slate-400 uppercase tracking-wider text-[11px] border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3 text-start">Asset</th>
                  <th className="py-2.5 px-3 text-start">Category</th>
                  <th className="py-2.5 px-3 text-end">Price</th>
                  <th className="py-2.5 px-3 text-end">24h Change</th>
                  <th className="py-2.5 px-3 text-end">24h Volume</th>
                  <th className="py-2.5 px-3 text-center">Signal</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredItems.map((item) => (
                  <tr
                    key={item.symbol}
                    onClick={() => onSelectSymbol?.(item.symbol)}
                    className={`hover:bg-slate-800/40 cursor-pointer transition-colors ${
                      selectedSymbol === item.symbol ? 'bg-amber-500/10' : ''
                    }`}
                  >
                    <td className="py-2.5 px-3 font-semibold text-white">
                      <div>{item.symbol}</div>
                      <div className="text-[10px] text-slate-500">{item.displayName}</div>
                    </td>
                    <td className="py-2.5 px-3 text-slate-400 font-mono text-[11px]">{item.category}</td>
                    <td className="py-2.5 px-3 text-end font-mono font-medium">
                      {item.price != null ? `$${item.price.toLocaleString()}` : '—'}
                    </td>
                    <td
                      className={`py-2.5 px-3 text-end font-bold font-mono ${
                        item.change24hPercent == null
                          ? 'text-slate-500'
                          : item.change24hPercent >= 0
                          ? 'text-emerald-400'
                          : 'text-rose-400'
                      }`}
                    >
                      {item.change24hPercent == null
                        ? '—'
                        : `${item.change24hPercent >= 0 ? '+' : ''}${item.change24hPercent.toFixed(2)}%`}
                    </td>
                    <td className="py-2.5 px-3 text-end text-slate-400 font-mono">
                      {item.volume24hUsd != null ? `$${(item.volume24hUsd / 1e9).toFixed(2)}B` : '—'}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      {item.signalAction ? (
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            item.signalAction === 'BUY'
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                              : item.signalAction === 'SELL'
                              ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                              : 'bg-slate-800 text-slate-400'
                          }`}
                        >
                          {item.signalAction}
                        </span>
                      ) : (
                        <span className="text-slate-500 font-mono text-[11px]">NO SIGNAL</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  );
};

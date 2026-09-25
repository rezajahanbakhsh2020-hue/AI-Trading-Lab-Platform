import React from 'react';
import { HeatmapTile } from '../../architecture/screener';

interface MarketHeatmapProps {
  tiles: HeatmapTile[];
  onSelectSymbol?: (symbol: string) => void;
  selectedSymbol?: string;
}

export const MarketHeatmap: React.FC<MarketHeatmapProps> = ({
  tiles,
  onSelectSymbol,
  selectedSymbol,
}) => {
  if (tiles.length === 0) {
    return (
      <div className="p-8 text-center text-slate-400 bg-slate-900/50 rounded-xl border border-slate-800">
        No market assets match the selected criteria.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
      {tiles.map((tile) => {
        const isSelected = selectedSymbol === tile.symbol;
        const bgOpacity = Math.max(0.2, Math.min(0.9, tile.intensity));
        const colorClass = tile.change24hPercent == null
          ? 'bg-slate-900/80 border-slate-800 text-slate-400'
          : tile.isPositive
          ? `bg-emerald-950/${Math.round(bgOpacity * 100)} border-emerald-500/40 text-emerald-300`
          : `bg-rose-950/${Math.round(bgOpacity * 100)} border-rose-500/40 text-rose-300`;

        return (
          <button
            key={tile.symbol}
            onClick={() => onSelectSymbol?.(tile.symbol)}
            className={`p-3.5 rounded-xl border transition-all text-start flex flex-col justify-between h-28 relative overflow-hidden group hover:scale-[1.02] cursor-pointer ${colorClass} ${
              isSelected ? 'ring-2 ring-amber-400 border-amber-400 shadow-lg' : ''
            }`}
          >
            <div className="flex items-center justify-between w-full min-w-0">
              <span className="font-bold text-sm tracking-wide text-white truncate min-w-0">{tile.symbol}</span>
              {tile.signalAction && (
                <span
                  className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider shrink-0 ${
                    tile.signalAction === 'BUY'
                      ? 'bg-emerald-500/30 text-emerald-200 border border-emerald-500/50'
                      : tile.signalAction === 'SELL'
                      ? 'bg-rose-500/30 text-rose-200 border border-rose-500/50'
                      : 'bg-slate-700/50 text-slate-300'
                  }`}
                >
                  {tile.signalAction}
                </span>
              )}
            </div>

            <div className="min-w-0">
              <div className="text-lg font-extrabold tracking-tight truncate" dir="ltr">
                {tile.change24hPercent != null
                  ? `${tile.isPositive ? '+' : ''}${tile.change24hPercent.toFixed(2)}%`
                  : '—'}
              </div>
              <div className="text-[11px] text-slate-400 truncate mt-0.5">{tile.displayName}</div>
            </div>
          </button>
        );
      })}
    </div>
  );
};

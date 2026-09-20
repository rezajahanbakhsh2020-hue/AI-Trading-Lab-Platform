import React, { useState } from 'react';
import { InteractiveChart } from './InteractiveChart';
import { MarketPulse } from './MarketPulse';
import { MarketScreener } from './MarketScreener';
import { SignalCard } from './SignalCard';
import { HostSnapshot } from '../../architecture/hostView';

interface IntelligenceWorkspaceProps {
  snapshot?: HostSnapshot | null;
  selectedSymbol?: string;
  onSelectSymbol?: (symbol: string) => void;
  onStageOrderIntent?: () => void;
  language?: string;
  isRtl?: boolean;
}

export const IntelligenceWorkspace: React.FC<IntelligenceWorkspaceProps> = ({
  snapshot,
  selectedSymbol = 'XAUUSD',
  onSelectSymbol,
  onStageOrderIntent,
}) => {
  const [activeSymbol, setActiveSymbol] = useState(selectedSymbol);

  const handleSymbolSelect = (sym: string) => {
    setActiveSymbol(sym);
    onSelectSymbol?.(sym);
  };

  const isConnected = snapshot?.project1?.connected ?? false;
  const quote = snapshot?.market?.quote;
  const quotePrice = quote?.last ?? quote?.mid ?? quote?.bid ?? snapshot?.risk?.entry ?? null;

  return (
    <div className="space-y-6">
      {/* Top Workspace Grid: Interactive Chart + Signal Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <InteractiveChart
            symbol={activeSymbol}
            timeframe={snapshot?.market?.timeframe || '1h'}
            candles={snapshot?.market?.candles || []}
            status={snapshot?.market?.status || 'disconnected'}
            provider={snapshot?.market?.provider || null}
            entryPrice={snapshot?.risk?.entry}
            stopLossPrice={snapshot?.risk?.stopLoss}
            takeProfits={snapshot?.risk?.takeProfits}
            isProviderConnected={isConnected}
          />
        </div>

        <div className="space-y-4">
          {snapshot ? (
            <SignalCard snapshot={snapshot} onStageOrderIntent={onStageOrderIntent} />
          ) : (
            <div className="p-4 text-center text-xs text-slate-400 bg-slate-950 rounded-lg border border-slate-800">
              No active signal snapshot available.
            </div>
          )}

          <MarketPulse quotePrice={quotePrice} change24hPct={quote?.changePercent} />
        </div>
      </div>

      {/* Bottom Section: Multi-Asset Market Screener & Heatmap */}
      <MarketScreener selectedSymbol={activeSymbol} onSelectSymbol={handleSymbolSelect} />
    </div>
  );
};

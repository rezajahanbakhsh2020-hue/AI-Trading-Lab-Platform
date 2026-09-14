import { useState } from "react";

type Timeframe = "1m" | "5m" | "15m" | "1h" | "4h" | "1D";
type ChartType = "Candles" | "Line" | "Area";

type ChartProps = {
  symbol?: string;
  entryPrice?: number | null;
  stopLossPrice?: number | null;
  takeProfits?: readonly number[];
  isProviderConnected?: boolean;
};

export function InteractiveChart({
  symbol = "XAUUSD",
  entryPrice,
  stopLossPrice,
  takeProfits = [],
  isProviderConnected = false,
}: ChartProps) {
  const [timeframe, setTimeframe] = useState<Timeframe>("1h");
  const [chartType, setChartType] = useState<ChartType>("Candles");
  const [hoverData, setHoverData] = useState<{
    x: number;
    ohlc: string;
    vol: string;
  } | null>(null);

  const timeframes: Timeframe[] = ["1m", "5m", "15m", "1h", "4h", "1D"];
  const chartTypes: ChartType[] = ["Candles", "Line", "Area"];

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    setHoverData({
      x,
      ohlc: "O: 2650.10 H: 2658.40 L: 2648.20 C: 2654.80",
      vol: "Vol: 12,450",
    });
  };

  const handleMouseLeave = () => {
    setHoverData(null);
  };

  return (
    <div className="chart-container">
      <div className="chart-toolbar">
        <div className="chart-toolbar-group">
          <span className="chart-symbol-tag">{symbol}</span>
          <div className="segmented-control">
            {timeframes.map((tf) => (
              <button
                key={tf}
                className={timeframe === tf ? "seg-btn active" : "seg-btn"}
                onClick={() => setTimeframe(tf)}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>

        <div className="chart-toolbar-group">
          <div className="segmented-control">
            {chartTypes.map((ct) => (
              <button
                key={ct}
                className={chartType === ct ? "seg-btn active" : "seg-btn"}
                onClick={() => setChartType(ct)}
              >
                {ct}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="chart-stage">
        {!isProviderConnected ? (
          <div className="chart-disconnected-overlay">
            <svg
              width="36"
              height="36"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <line x1="1" y1="1" x2="23" y2="23" />
              <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
              <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
              <path d="M10.71 5.05A16 16 0 0 1 22.58 9" />
              <path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" />
              <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
              <line x1="12" y1="20" x2="12.01" y2="20" />
            </svg>
            <p className="overlay-title">Market Data Provider Disconnected</p>
            <p className="overlay-sub">
              Candlestick and volume panes consume live market data through
              ProviderRegistry. No live candles attached.
            </p>
          </div>
        ) : null}

        {/* SVG Grid and Overlay Layer */}
        <svg
          className="chart-svg"
          viewBox="0 0 800 320"
          preserveAspectRatio="none"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          {/* Grid lines */}
          <line x1="0" y1="60" x2="800" y2="60" className="chart-grid-line" />
          <line x1="0" y1="120" x2="800" y2="120" className="chart-grid-line" />
          <line x1="0" y1="180" x2="800" y2="180" className="chart-grid-line" />
          <line x1="0" y1="240" x2="800" y2="240" className="chart-grid-line" />

          {/* Crosshair when hover */}
          {hoverData && (
            <line
              x1={hoverData.x}
              y1="0"
              x2={hoverData.x}
              y2="320"
              stroke="rgba(255,255,255,0.2)"
              strokeDasharray="2 2"
            />
          )}

          {/* Risk Level Overlay Lines when available */}
          {entryPrice && (
            <g>
              <line
                x1="0"
                y1="140"
                x2="800"
                y2="140"
                stroke="#3B82F6"
                strokeWidth="1.5"
                strokeDasharray="4 4"
              />
              <text x="12" y="135" fill="#3B82F6" fontSize="11" fontWeight="bold">
                Entry: {entryPrice}
              </text>
            </g>
          )}

          {stopLossPrice && (
            <g>
              <line
                x1="0"
                y1="220"
                x2="800"
                y2="220"
                stroke="#EF4444"
                strokeWidth="1.5"
                strokeDasharray="3 3"
              />
              <text x="12" y="215" fill="#EF4444" fontSize="11" fontWeight="bold">
                SL: {stopLossPrice}
              </text>
            </g>
          )}

          {takeProfits.map((tp, idx) => (
            <g key={idx}>
              <line
                x1="0"
                y1={80 - idx * 20}
                x2="800"
                y2={80 - idx * 20}
                stroke="#10B981"
                strokeWidth="1.5"
                strokeDasharray="3 3"
              />
              <text
                x="12"
                y={75 - idx * 20}
                fill="#10B981"
                fontSize="11"
                fontWeight="bold"
              >
                TP{idx + 1}: {tp}
              </text>
            </g>
          ))}
        </svg>
      </div>

      <div className="chart-footer">
        <div className="chart-status-label">
          <span className="dot warn" /> Provider: Unconnected
        </div>
        <div className="chart-status-label">
          {hoverData ? hoverData.ohlc : `Timeframe: ${timeframe}`}
        </div>
      </div>
    </div>
  );
}

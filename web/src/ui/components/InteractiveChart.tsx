import { useState } from "react";
import type { Candle, MarketDataStatus, ProviderMetadata } from "../../architecture/marketData";
import { useI18n } from "../../i18n";

type Timeframe = "1m" | "5m" | "15m" | "30m" | "1h" | "4h" | "1d";
type ChartType = "Candles" | "Line" | "Area";

type ChartProps = {
  symbol?: string;
  timeframe?: string;
  candles?: readonly Candle[];
  status?: MarketDataStatus;
  provider?: ProviderMetadata | null;
  errorMessage?: string | null;
  entryPrice?: number | null;
  stopLossPrice?: number | null;
  takeProfits?: readonly number[];
  isProviderConnected?: boolean;
  onTimeframeChange?: (tf: string) => void;
  onRefresh?: () => void;
};

export function InteractiveChart({
  symbol = "XAUUSD",
  timeframe = "1h",
  candles = [],
  status = "disconnected",
  provider = null,
  errorMessage = null,
  entryPrice,
  stopLossPrice,
  takeProfits = [],
  isProviderConnected = false,
  onTimeframeChange,
  onRefresh,
}: ChartProps) {
  const { t } = useI18n();
  const [selectedTimeframe, setSelectedTimeframe] = useState<Timeframe>(
    (timeframe as Timeframe) || "1h"
  );
  const [chartType, setChartType] = useState<ChartType>("Candles");
  const [hoverData, setHoverData] = useState<{
    x: number;
    ohlc: string;
    vol: string;
  } | null>(null);

  const timeframes: Timeframe[] = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"];
  const chartTypes: ChartType[] = ["Candles", "Line", "Area"];

  const handleTimeframeClick = (tf: Timeframe) => {
    setSelectedTimeframe(tf);
    if (onTimeframeChange) {
      onTimeframeChange(tf);
    }
  };

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!candles || candles.length === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const idx = Math.min(
      candles.length - 1,
      Math.max(0, Math.floor((x / rect.width) * candles.length))
    );
    const c = candles[idx];
    if (c) {
      const volStr = c.volume != null ? `Vol: ${c.volume.toLocaleString()}` : "Vol: N/A";
      setHoverData({
        x: (idx + 0.5) * (800 / candles.length),
        ohlc: `O: ${c.open.toFixed(2)} H: ${c.high.toFixed(2)} L: ${c.low.toFixed(2)} C: ${c.close.toFixed(2)}`,
        vol: volStr,
      });
    }
  };

  const handleMouseLeave = () => {
    setHoverData(null);
  };

  // Compute price bounds for rendering candles if present
  let minPrice = Infinity;
  let maxPrice = -Infinity;
  if (candles && candles.length > 0) {
    candles.forEach((c) => {
      if (c.low < minPrice) minPrice = c.low;
      if (c.high > maxPrice) maxPrice = c.high;
    });
  }
  if (entryPrice) {
    minPrice = Math.min(minPrice, entryPrice);
    maxPrice = Math.max(maxPrice, entryPrice);
  }
  if (stopLossPrice) {
    minPrice = Math.min(minPrice, stopLossPrice);
    maxPrice = Math.max(maxPrice, stopLossPrice);
  }
  takeProfits.forEach((tp) => {
    minPrice = Math.min(minPrice, tp);
    maxPrice = Math.max(maxPrice, tp);
  });

  if (minPrice === Infinity || maxPrice === -Infinity || minPrice === maxPrice) {
    minPrice = 2600;
    maxPrice = 2700;
  }
  const pricePadding = (maxPrice - minPrice) * 0.05 || 10;
  minPrice -= pricePadding;
  maxPrice += pricePadding;

  const chartWidth = 800;
  const chartHeight = 320;
  const candleAreaHeight = 240;

  const getY = (price: number) => {
    return (
      candleAreaHeight -
      ((price - minPrice) / (maxPrice - minPrice)) * candleAreaHeight
    );
  };

  const hasCandles = candles && candles.length > 0;
  const candleWidth = hasCandles ? Math.max(2, (chartWidth / candles.length) * 0.6) : 0;
  const candleStep = hasCandles ? chartWidth / candles.length : 0;

  // Compute line path and area path
  let linePath = "";
  let areaPath = "";
  if (hasCandles) {
    const points = candles.map((c, i) => {
      const x = (i + 0.5) * candleStep;
      const y = getY(c.close);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    linePath = `M ${points.join(" L ")}`;
    areaPath = `${linePath} L ${chartWidth},${candleAreaHeight} L 0,${candleAreaHeight} Z`;
  }

  const showOverlay = !isProviderConnected || status !== "connected" || !hasCandles;

  return (
    <div className="chart-container">
      <div className="chart-toolbar">
        <div className="chart-toolbar-group">
          <span className="chart-symbol-tag">{symbol}</span>
          <div className="segmented-control">
            {timeframes.map((tf) => (
              <button
                key={tf}
                className={selectedTimeframe === tf ? "seg-btn active" : "seg-btn"}
                onClick={() => handleTimeframeClick(tf)}
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
          {onRefresh && (
            <button
              className="btn btn-secondary"
              style={{ fontSize: 11, padding: "4px 8px" }}
              onClick={onRefresh}
            >
              {t("buttons.refresh")}
            </button>
          )}
        </div>
      </div>

      <div className="chart-stage">
        {showOverlay && (
          <div className="chart-disconnected-overlay">
            {status === "loading" ? (
              <>
                <p className="overlay-title">{t("chart.streamingData")}...</p>
                <p className="overlay-sub">Connecting to ProviderRegistry to stream {symbol} candles.</p>
              </>
            ) : status === "error" ? (
              <>
                <p className="overlay-title" style={{ color: "#EF4444" }}>Provider Error</p>
                <p className="overlay-sub">{errorMessage || "Failed to fetch candles from provider."}</p>
              </>
            ) : status === "stale" ? (
              <>
                <p className="overlay-title" style={{ color: "#F59E0B" }}>Data Stale</p>
                <p className="overlay-sub">Market data age exceeded freshness threshold.</p>
              </>
            ) : !isProviderConnected ? (
              <>
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
                <p className="overlay-title">{t("chart.disconnectedOverlayTitle")}</p>
                <p className="overlay-sub">
                  {t("chart.disconnectedOverlaySub")}
                </p>
              </>
            ) : (
              <>
                <p className="overlay-title">No Candles Available</p>
                <p className="overlay-sub">Provider returned no OHLC records for {symbol} ({selectedTimeframe}).</p>
              </>
            )}
          </div>
        )}

        {/* SVG Grid and Candle/Line Layer */}
        <svg
          className="chart-svg"
          viewBox={`0 0 ${chartWidth} ${chartHeight}`}
          preserveAspectRatio="none"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          {/* Price Horizontal Grid lines */}
          {[0.2, 0.4, 0.6, 0.8].map((ratio) => (
            <g key={ratio}>
              <line
                x1="0"
                y1={candleAreaHeight * ratio}
                x2={chartWidth}
                y2={candleAreaHeight * ratio}
                className="chart-grid-line"
              />
              <text
                x={chartWidth - 50}
                y={candleAreaHeight * ratio - 4}
                fill="rgba(255,255,255,0.3)"
                fontSize="10"
              >
                {(maxPrice - ratio * (maxPrice - minPrice)).toFixed(1)}
              </text>
            </g>
          ))}

          {/* Render Real Candle Data if Present */}
          {hasCandles && chartType === "Candles" && (
            <g>
              {candles.map((c, i) => {
                const x = (i + 0.5) * candleStep;
                const openY = getY(c.open);
                const closeY = getY(c.close);
                const highY = getY(c.high);
                const lowY = getY(c.low);
                const isBullish = c.close >= c.open;
                const color = isBullish ? "#10B981" : "#EF4444";
                const bodyTop = Math.min(openY, closeY);
                const bodyHeight = Math.max(1, Math.abs(closeY - openY));

                return (
                  <g key={i}>
                    {/* Wick */}
                    <line x1={x} y1={highY} x2={x} y2={lowY} stroke={color} strokeWidth="1" />
                    {/* Body */}
                    <rect
                      x={x - candleWidth / 2}
                      y={bodyTop}
                      width={candleWidth}
                      height={bodyHeight}
                      fill={color}
                      rx="0.5"
                    />
                    {/* Volume Bar */}
                    {c.volume != null && (
                      <rect
                        x={x - candleWidth / 2}
                        y={chartHeight - Math.min(60, (c.volume / 20000) * 60)}
                        width={candleWidth}
                        height={Math.min(60, (c.volume / 20000) * 60)}
                        fill={isBullish ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)"}
                      />
                    )}
                  </g>
                );
              })}
            </g>
          )}

          {/* Render Line Chart */}
          {hasCandles && chartType === "Line" && (
            <path d={linePath} fill="none" stroke="#3B82F6" strokeWidth="2" />
          )}

          {/* Render Area Chart */}
          {hasCandles && chartType === "Area" && (
            <g>
              <path d={areaPath} fill="rgba(59, 130, 246, 0.15)" />
              <path d={linePath} fill="none" stroke="#3B82F6" strokeWidth="2" />
            </g>
          )}

          {/* Crosshair when hover */}
          {hoverData && (
            <line
              x1={hoverData.x}
              y1="0"
              x2={hoverData.x}
              y2={chartHeight}
              stroke="rgba(255,255,255,0.25)"
              strokeDasharray="2 2"
            />
          )}

          {/* Risk Level Overlay Lines when available */}
          {entryPrice != null && (
            <g>
              <line
                x1="0"
                y1={getY(entryPrice)}
                x2={chartWidth}
                y2={getY(entryPrice)}
                stroke="#3B82F6"
                strokeWidth="1.5"
                strokeDasharray="4 4"
              />
              <text x="12" y={getY(entryPrice) - 4} fill="#3B82F6" fontSize="11" fontWeight="bold">
                {t("chart.legend.entry")}: {entryPrice.toFixed(2)}
              </text>
            </g>
          )}

          {stopLossPrice != null && (
            <g>
              <line
                x1="0"
                y1={getY(stopLossPrice)}
                x2={chartWidth}
                y2={getY(stopLossPrice)}
                stroke="#EF4444"
                strokeWidth="1.5"
                strokeDasharray="3 3"
              />
              <text x="12" y={getY(stopLossPrice) - 4} fill="#EF4444" fontSize="11" fontWeight="bold">
                {t("chart.legend.sl")}: {stopLossPrice.toFixed(2)}
              </text>
            </g>
          )}

          {takeProfits.map((tp, idx) => (
            <g key={idx}>
              <line
                x1="0"
                y1={getY(tp)}
                x2={chartWidth}
                y2={getY(tp)}
                stroke="#10B981"
                strokeWidth="1.5"
                strokeDasharray="3 3"
              />
              <text x="12" y={getY(tp) - 4} fill="#10B981" fontSize="11" fontWeight="bold">
                {t("chart.legend.tp")} {idx + 1}: {tp.toFixed(2)}
              </text>
            </g>
          ))}
        </svg>
      </div>

      <div className="chart-footer">
        <div className="chart-status-label">
          <span
            className={`dot ${
              status === "connected"
                ? "ready"
                : status === "stale" || status === "loading"
                ? "warn"
                : "disconnected"
            }`}
          />
          {t("nav.providers")}: {provider ? provider.name : isProviderConnected ? t("status.connected") : t("status.disconnected")}
        </div>
        <div className="chart-status-label">
          {hoverData ? `${hoverData.ohlc} | ${hoverData.vol}` : `${t("markets.timeframe")}: ${selectedTimeframe} (${candles.length} bars)`}
        </div>
      </div>
    </div>
  );
}

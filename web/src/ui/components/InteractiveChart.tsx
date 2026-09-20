import { useEffect, useRef, useState, useId } from "react";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  AreaSeries,
  HistogramSeries,
  createSeriesMarkers,
  ColorType,
  LineStyle,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type SingleValueData,
  type CandlestickData,
  type SeriesMarker,
} from "lightweight-charts";
import type { Candle, MarketDataStatus, ProviderMetadata } from "../../architecture/marketData";
import { useI18n } from "../../i18n";

export type Timeframe = "1m" | "5m" | "15m" | "30m" | "1h" | "4h" | "1d";
export type ChartType = "Candles" | "Line" | "Area";

export interface InteractiveChartProps {
  symbol?: string;
  timeframe?: string;
  candles?: readonly Candle[];
  status?: MarketDataStatus;
  provider?: ProviderMetadata | null;
  errorMessage?: string | null;
  entryPrice?: number | null;
  stopLossPrice?: number | null;
  takeProfits?: readonly number[];
  signalAction?: string | null;
  signalTime?: number | null;
  isProviderConnected?: boolean;
  onTimeframeChange?: (tf: string) => void;
  onRefresh?: () => void;
}

/**
 * Parses timestamp value into Unix seconds (number).
 * Supports numeric seconds, numeric milliseconds, ISO-8601 strings, or numeric strings.
 */
function parseTimestampToUnixSeconds(ts: number | string | unknown): number {
  if (typeof ts === "number") {
    if (!Number.isFinite(ts)) return NaN;
    return ts > 1e11 ? Math.floor(ts / 1000) : ts;
  }
  if (typeof ts === "string") {
    const trimmed = ts.trim();
    if (!trimmed) return NaN;
    const parsedDate = Date.parse(trimmed);
    if (!Number.isNaN(parsedDate)) {
      return Math.floor(parsedDate / 1000);
    }
    const num = Number(trimmed);
    if (Number.isFinite(num)) {
      return num > 1e11 ? Math.floor(num / 1000) : num;
    }
  }
  return NaN;
}

/**
 * Normalizes candle timestamps to strictly ascending Time values.
 * Lightweight Charts requires sorted unique timestamps.
 */
function normalizeCandles(candles: readonly Candle[]) {
  if (!candles || candles.length === 0) return [];

  const parsed: Candle[] = [];

  for (const c of candles) {
    if (
      !c ||
      typeof c.open !== "number" ||
      !Number.isFinite(c.open) ||
      typeof c.high !== "number" ||
      !Number.isFinite(c.high) ||
      typeof c.low !== "number" ||
      !Number.isFinite(c.low) ||
      typeof c.close !== "number" ||
      !Number.isFinite(c.close)
    ) {
      continue;
    }

    const unixSec = parseTimestampToUnixSeconds(c.timestamp);
    if (Number.isNaN(unixSec) || !Number.isFinite(unixSec)) {
      continue;
    }

    parsed.push({
      ...c,
      timestamp: unixSec,
    });
  }

  if (parsed.length === 0) return [];

  const sorted = [...parsed].sort((a, b) => (a.timestamp as number) - (b.timestamp as number));
  const result: Candle[] = [];
  const seenTimestamps = new Set<number>();

  for (const c of sorted) {
    const ts = c.timestamp as number;
    if (!seenTimestamps.has(ts)) {
      seenTimestamps.add(ts);
      result.push(c);
    }
  }

  return result;
}

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
  signalAction,
  signalTime,
  isProviderConnected = false,
  onTimeframeChange,
  onRefresh,
}: InteractiveChartProps) {
  const { t } = useI18n();
  const [selectedTimeframe, setSelectedTimeframe] = useState<Timeframe>(
    (timeframe as Timeframe) || "1h"
  );

  useEffect(() => {
    if (timeframe && timeframe !== selectedTimeframe) {
      setSelectedTimeframe(timeframe as Timeframe);
    }
  }, [timeframe]);
  const [chartType, setChartType] = useState<ChartType>("Candles");
  const [hoverData, setHoverData] = useState<{
    timeStr: string;
    ohlcStr: string;
    volStr: string;
  } | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const chartApiRef = useRef<IChartApi | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mainSeriesRef = useRef<ISeriesApi<any> | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const volumeSeriesRef = useRef<ISeriesApi<any> | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);

  const timeframes: Timeframe[] = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"];
  const chartTypes: ChartType[] = ["Candles", "Line", "Area"];

  // Unique chart container ID for accessibility
  const containerId = useId();

  const handleTimeframeClick = (tf: Timeframe) => {
    setSelectedTimeframe(tf);
    if (onTimeframeChange) {
      onTimeframeChange(tf);
    }
  };

  const cleanCandles = normalizeCandles(candles);
  const hasCandles = cleanCandles.length > 0;
  const isDataAvailable = isProviderConnected && status === "connected" && hasCandles;

  // Initialize Lightweight Chart instance
  useEffect(() => {
    if (!containerRef.current) return;

    if (chartApiRef.current) {
      try {
        chartApiRef.current.remove();
      } catch {
        // ignore removal errors on stale instances
      }
      chartApiRef.current = null;
      mainSeriesRef.current = null;
      volumeSeriesRef.current = null;
    }

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = Math.max(300, container.clientHeight || 340);

    // If container has 0 width (e.g., hidden tab or before layout mount), defer chart creation
    if (width <= 0) {
      const observer = new ResizeObserver((entries) => {
        const entry = entries[0];
        if (entry && entry.contentRect.width > 0 && !chartApiRef.current && containerRef.current) {
          observer.disconnect();
          setRenderError(null);
        }
      });
      observer.observe(container);
      return () => observer.disconnect();
    }

    let chart: IChartApi | null = null;
    try {
      chart = createChart(container, {
        width,
        height,
        layout: {
          background: { type: ColorType.Solid, color: "#0F172A" },
          textColor: "#94A3B8",
          fontSize: 11,
          fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        },
        grid: {
          vertLines: { color: "rgba(255, 255, 255, 0.05)" },
          horzLines: { color: "rgba(255, 255, 255, 0.05)" },
        },
        crosshair: {
          mode: CrosshairMode.Normal,
          vertLine: {
            color: "rgba(255, 255, 255, 0.3)",
            width: 1,
            style: LineStyle.Dashed,
            labelBackgroundColor: "#1E293B",
          },
          horzLine: {
            color: "rgba(255, 255, 255, 0.3)",
            width: 1,
            style: LineStyle.Dashed,
            labelBackgroundColor: "#1E293B",
          },
        },
        rightPriceScale: {
          borderColor: "rgba(255, 255, 255, 0.1)",
          autoScale: true,
          alignLabels: true,
          borderVisible: true,
          scaleMargins: {
            top: 0.1,
            bottom: 0.2,
          },
        },
        timeScale: {
          borderColor: "rgba(255, 255, 255, 0.1)",
          timeVisible: true,
          secondsVisible: false,
          borderVisible: true,
          barSpacing: 8,
          minBarSpacing: 3,
          rightOffset: 5,
        },
      });
      chartApiRef.current = chart;
      setRenderError(null);
    } catch (err: any) {
      setRenderError(err?.message || "Failed to initialize financial chart canvas.");
      return;
    }

    const handleResize = () => {
      if (chartApiRef.current && containerRef.current && containerRef.current.clientWidth > 0) {
        chartApiRef.current.applyOptions({
          width: containerRef.current.clientWidth,
          height: Math.max(300, containerRef.current.clientHeight || 340),
        });
      }
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      if (chartApiRef.current) {
        try {
          chartApiRef.current.remove();
        } catch {
          // ignore removal errors
        }
        chartApiRef.current = null;
        mainSeriesRef.current = null;
        volumeSeriesRef.current = null;
      }
    };
  }, []);

  // Update Series, Data, Overlays whenever inputs change
  useEffect(() => {
    const chart = chartApiRef.current;
    if (!chart) return;

    try {
      if (mainSeriesRef.current) {
        try {
          chart.removeSeries(mainSeriesRef.current);
        } catch {
          // ignore series removal failure
        }
        mainSeriesRef.current = null;
      }
      if (volumeSeriesRef.current) {
        try {
          chart.removeSeries(volumeSeriesRef.current);
        } catch {
          // ignore series removal failure
        }
        volumeSeriesRef.current = null;
      }

      if (!isDataAvailable) return;

      // 1. Add Main Price Series (Candles, Line, or Area)
      if (chartType === "Candles") {
        const series = chart.addSeries(CandlestickSeries, {
          upColor: "#10B981",
          downColor: "#EF4444",
          borderVisible: false,
          wickUpColor: "#10B981",
          wickDownColor: "#EF4444",
        });

        const formattedCandles: CandlestickData[] = cleanCandles.map((c) => ({
          time: c.timestamp as Time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        }));

        series.setData(formattedCandles);
        mainSeriesRef.current = series;
      } else if (chartType === "Line") {
        const series = chart.addSeries(LineSeries, {
          color: "#3B82F6",
          lineWidth: 2,
        });

        const formattedLine: SingleValueData[] = cleanCandles.map((c) => ({
          time: c.timestamp as Time,
          value: c.close,
        }));

        series.setData(formattedLine);
        mainSeriesRef.current = series;
      } else if (chartType === "Area") {
        const series = chart.addSeries(AreaSeries, {
          topColor: "rgba(59, 130, 246, 0.4)",
          bottomColor: "rgba(59, 130, 246, 0.0)",
          lineColor: "#3B82F6",
          lineWidth: 2,
        });

        const formattedArea: SingleValueData[] = cleanCandles.map((c) => ({
          time: c.timestamp as Time,
          value: c.close,
        }));

        series.setData(formattedArea);
        mainSeriesRef.current = series;
      }

      // 2. Add Volume Histogram Pane if volume exists
      const hasVolume = cleanCandles.some((c) => c.volume != null && c.volume > 0);
      if (hasVolume) {
        chart.priceScale("right").applyOptions({
          scaleMargins: {
            top: 0.08,
            bottom: 0.22,
          },
        });

        const volumeSeries = chart.addSeries(HistogramSeries, {
          priceFormat: { type: "volume" },
          priceScaleId: "volume_scale",
        });

        chart.priceScale("volume_scale").applyOptions({
          scaleMargins: {
            top: 0.8,
            bottom: 0,
          },
        });

        const volumeData = cleanCandles.map((c) => ({
          time: c.timestamp as Time,
          value: c.volume ?? 0,
          color: c.close >= c.open ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)",
        }));

        volumeSeries.setData(volumeData);
        volumeSeriesRef.current = volumeSeries;
      } else {
        chart.priceScale("right").applyOptions({
          scaleMargins: {
            top: 0.08,
            bottom: 0.08,
          },
        });
      }

      // 3. Project 1 Price Level Overlays (Entry, SL, TP1..TP3)
      const mainSeries = mainSeriesRef.current;
      if (mainSeries) {
        if (entryPrice != null && Number.isFinite(entryPrice)) {
          mainSeries.createPriceLine({
            price: entryPrice,
            color: "#3B82F6",
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: `Project 1 Entry: ${entryPrice.toFixed(2)}`,
          });
        }

        if (stopLossPrice != null && Number.isFinite(stopLossPrice)) {
          mainSeries.createPriceLine({
            price: stopLossPrice,
            color: "#EF4444",
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: `Project 1 SL: ${stopLossPrice.toFixed(2)}`,
          });
        }

        takeProfits.forEach((tp, idx) => {
          if (tp != null && Number.isFinite(tp)) {
            mainSeries.createPriceLine({
              price: tp,
              color: "#10B981",
              lineWidth: 1,
              lineStyle: LineStyle.Dashed,
              axisLabelVisible: true,
              title: `Project 1 TP${idx + 1}: ${tp.toFixed(2)}`,
            });
          }
        });

        // 4. Project 1 Signal Event Markers
        if (signalAction && cleanCandles.length > 0) {
          const lastCandleTime = signalTime && Number.isFinite(signalTime)
            ? (signalTime as Time)
            : (cleanCandles[cleanCandles.length - 1].timestamp as Time);

          const isBuy = signalAction.toUpperCase().includes("BUY") || signalAction.toUpperCase().includes("LONG");

          const markers: SeriesMarker<Time>[] = [
            {
              time: lastCandleTime,
              position: isBuy ? "belowBar" : "aboveBar",
              color: isBuy ? "#10B981" : "#EF4444",
              shape: isBuy ? "arrowUp" : "arrowDown",
              text: `P1 Signal: ${signalAction}`,
            },
          ];

          createSeriesMarkers(mainSeries, markers);
        }
      }

      // 5. Crosshair listener for Legend / Tooltip
      chart.subscribeCrosshairMove((param) => {
        if (!param.time || param.point === undefined || param.point.x < 0 || param.point.y < 0) {
          setHoverData(null);
          return;
        }

        const candleMatch = cleanCandles.find((c) => c.timestamp === (param.time as number));
        if (candleMatch) {
          const volText = candleMatch.volume != null ? `Vol: ${candleMatch.volume.toLocaleString()}` : "Vol: N/A";
          setHoverData({
            timeStr: new Date(candleMatch.timestamp * 1000).toUTCString().slice(5, 22),
            ohlcStr: `O: ${candleMatch.open.toFixed(2)} H: ${candleMatch.high.toFixed(2)} L: ${candleMatch.low.toFixed(2)} C: ${candleMatch.close.toFixed(2)}`,
            volStr: volText,
          });
        }
      });

      chart.timeScale().fitContent();
    } catch (err: any) {
      setRenderError(err?.message || "Error rendering financial data on chart.");
    }
  }, [cleanCandles, chartType, isDataAvailable, entryPrice, stopLossPrice, takeProfits, signalAction, signalTime]);

  const showOverlay = !isProviderConnected || status !== "connected" || !hasCandles;

  return (
    <div className="chart-container" id={`chart-root-${containerId}`}>
      {/* Chart Toolbar */}
      <div className="chart-toolbar">
        <div className="chart-toolbar-group">
          <span className="chart-symbol-tag">{symbol}</span>
          <div className="segmented-control" role="group" aria-label="Timeframe selector">
            {timeframes.map((tf) => (
              <button
                key={tf}
                className={selectedTimeframe === tf ? "seg-btn active" : "seg-btn"}
                onClick={() => handleTimeframeClick(tf)}
                type="button"
              >
                {tf}
              </button>
            ))}
          </div>
        </div>

        <div className="chart-toolbar-group">
          <div className="segmented-control" role="group" aria-label="Chart type selector">
            {chartTypes.map((ct) => (
              <button
                key={ct}
                className={chartType === ct ? "seg-btn active" : "seg-btn"}
                onClick={() => setChartType(ct)}
                type="button"
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
              type="button"
            >
              {t("buttons.refresh")}
            </button>
          )}
        </div>
      </div>

      {/* Lightweight Chart Canvas Stage */}
      <div className="chart-stage" style={{ position: "relative", minHeight: 340 }}>
        {(showOverlay || renderError != null) && (
          <div className="chart-disconnected-overlay">
            {renderError != null ? (
              <>
                <p className="overlay-title" style={{ color: "#EF4444" }}>Chart Rendering Failure</p>
                <p className="overlay-sub">{renderError}</p>
              </>
            ) : status === "loading" ? (
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

        {/* Lightweight Charts Canvas Host Container */}
        <div
          ref={containerRef}
          className="lightweight-chart-host"
          style={{ width: "100%", height: "100%", minHeight: 340 }}
        />
      </div>

      {/* Chart Footer / Crosshair Legend */}
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
          {hoverData
            ? `${hoverData.timeStr} | ${hoverData.ohlcStr} | ${hoverData.volStr}`
            : `${t("markets.timeframe")}: ${selectedTimeframe} (${cleanCandles.length} bars)`}
        </div>
      </div>
    </div>
  );
}

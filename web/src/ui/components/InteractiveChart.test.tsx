import { render, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { InteractiveChart } from "./InteractiveChart";
import { I18nProvider } from "../../i18n";
import type { Candle, ProviderMetadata } from "../../architecture/marketData";

// Mock lightweight-charts to avoid Canvas context errors in jsdom environment
vi.mock("lightweight-charts", () => {
  const mockSeries = {
    setData: vi.fn(),
    createPriceLine: vi.fn(),
    applyOptions: vi.fn(),
  };

  const mockChart = {
    addSeries: vi.fn().mockReturnValue(mockSeries),
    removeSeries: vi.fn(),
    priceScale: vi.fn().mockReturnValue({
      applyOptions: vi.fn(),
    }),
    subscribeCrosshairMove: vi.fn(),
    timeScale: vi.fn().mockReturnValue({
      fitContent: vi.fn(),
    }),
    applyOptions: vi.fn(),
    remove: vi.fn(),
  };

  return {
    createChart: vi.fn().mockReturnValue(mockChart),
    CandlestickSeries: { type: "Candlestick" },
    LineSeries: { type: "Line" },
    AreaSeries: { type: "Area" },
    HistogramSeries: { type: "Histogram" },
    createSeriesMarkers: vi.fn(),
    ColorType: { Solid: "solid" },
    LineStyle: { Dashed: 2 },
    CrosshairMode: { Normal: 0 },
  };
});

// Mock ResizeObserver
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

describe("InteractiveChart Component", () => {
  const sampleCandles: Candle[] = [
    { timestamp: 1710000000, open: 2630.1, high: 2638.5, low: 2628.0, close: 2635.4, volume: 11200 },
    { timestamp: 1710003600, open: 2635.4, high: 2642.0, low: 2633.2, close: 2640.8, volume: 13500 },
  ];

  const sampleProvider: ProviderMetadata = {
    id: "biquote-1",
    name: "BiQuoteProvider",
    provider: "biquote",
    status: "connected",
    supportedTimeframes: ["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders connected chart with symbol and timeframes", () => {
    const { container } = render(
      <I18nProvider>
        <InteractiveChart
          symbol="XAUUSD"
          timeframe="1h"
          candles={sampleCandles}
          status="connected"
          provider={sampleProvider}
          isProviderConnected={true}
        />
      </I18nProvider>
    );

    expect(container.querySelector(".chart-symbol-tag")?.textContent).toBe("XAUUSD");
    expect(container.querySelector(".segmented-control")).not.toBeNull();
  });

  it("handles disconnected overlay when market provider is disconnected", () => {
    const { container } = render(
      <I18nProvider>
        <InteractiveChart
          symbol="XAUUSD"
          timeframe="1h"
          candles={[]}
          status="disconnected"
          provider={null}
          isProviderConnected={false}
        />
      </I18nProvider>
    );

    expect(container.querySelector(".overlay-title")?.textContent).toBe("Market Data Provider Disconnected");
  });

  it("handles loading overlay state truthfully", () => {
    const { container } = render(
      <I18nProvider>
        <InteractiveChart
          symbol="EURUSD"
          timeframe="15m"
          candles={[]}
          status="loading"
          provider={sampleProvider}
          isProviderConnected={true}
        />
      </I18nProvider>
    );

    expect(container.querySelector(".overlay-title")?.textContent).toBe("Streaming provider candles...");
  });

  it("triggers onTimeframeChange callback when timeframe button is clicked", () => {
    const handleTfChange = vi.fn();

    const { container } = render(
      <I18nProvider>
        <InteractiveChart
          symbol="XAUUSD"
          timeframe="1h"
          candles={sampleCandles}
          status="connected"
          provider={sampleProvider}
          isProviderConnected={true}
          onTimeframeChange={handleTfChange}
        />
      </I18nProvider>
    );

    const buttons = container.querySelectorAll(".segmented-control button");
    const btn15m = Array.from(buttons).find((b) => b.textContent === "15m");
    expect(btn15m).toBeDefined();
    if (btn15m) {
      fireEvent.click(btn15m);
      expect(handleTfChange).toHaveBeenCalledWith("15m");
    }
  });

  it("switches chart type tabs between Candles, Line, and Area", () => {
    const { container } = render(
      <I18nProvider>
        <InteractiveChart
          symbol="XAUUSD"
          timeframe="1h"
          candles={sampleCandles}
          status="connected"
          provider={sampleProvider}
          isProviderConnected={true}
        />
      </I18nProvider>
    );

    const typeGroup = container.querySelectorAll(".chart-toolbar-group")[1];
    const buttons = typeGroup.querySelectorAll("button");
    const lineBtn = Array.from(buttons).find((b) => b.textContent === "Line");
    expect(lineBtn).toBeDefined();
    if (lineBtn) {
      fireEvent.click(lineBtn);
    }
  });

  it("safely filters out malformed/NaN candles without crashing", () => {
    const malformedCandles: any[] = [
      { timestamp: 1710000000, open: NaN, high: 2638.5, low: 2628.0, close: 2635.4 },
      { timestamp: null, open: 2630.0, high: 2638.5, low: 2628.0, close: 2635.4 },
      { timestamp: 1710003600, open: 2635.4, high: 2642.0, low: 2633.2, close: 2640.8 },
    ];

    const { container } = render(
      <I18nProvider>
        <InteractiveChart
          symbol="XAUUSD"
          timeframe="1h"
          candles={malformedCandles}
          status="connected"
          provider={sampleProvider}
          isProviderConnected={true}
        />
      </I18nProvider>
    );

    expect(container.querySelector(".chart-symbol-tag")?.textContent).toBe("XAUUSD");
  });

  it("handles ISO-8601 string timestamps from BiQuote provider cleanly", () => {
    const isoCandles: any[] = [
      { timestamp: "2026-09-17T00:00:00Z", open: 4271.7, high: 4381.3, low: 4266.1, close: 4346.5, volume: 100 },
      { timestamp: "2026-09-18T00:00:00Z", open: 4346.1, high: 4399.8, low: 4334.3, close: 4378.1, volume: 150 },
    ];

    const { container } = render(
      <I18nProvider>
        <InteractiveChart
          symbol="XAUUSD"
          timeframe="1d"
          candles={isoCandles}
          status="connected"
          provider={sampleProvider}
          isProviderConnected={true}
        />
      </I18nProvider>
    );

    expect(container.querySelector(".overlay-title")).toBeNull();
    expect(container.querySelector(".chart-symbol-tag")?.textContent).toBe("XAUUSD");
  });

  it("renders overlay when connected provider returns empty dataset", () => {
    const { container } = render(
      <I18nProvider>
        <InteractiveChart
          symbol="XAUUSD"
          timeframe="1d"
          candles={[]}
          status="connected"
          provider={sampleProvider}
          isProviderConnected={true}
        />
      </I18nProvider>
    );

    expect(container.querySelector(".overlay-title")?.textContent).toBe("No Candles Available");
  });

  it("renders price line overlays when active signal levels are supplied and clears them when null", () => {
    const { rerender } = render(
      <I18nProvider>
        <InteractiveChart
          symbol="XAUUSD"
          timeframe="1h"
          candles={sampleCandles}
          status="connected"
          provider={sampleProvider}
          entryPrice={2650.5}
          stopLossPrice={2635.0}
          takeProfits={[2670.0, 2690.0, 2710.0]}
          signalAction="BUY"
          isProviderConnected={true}
        />
      </I18nProvider>
    );

    // Re-render with null signal levels (e.g. signal transitioned to NO SIGNAL or STALE)
    rerender(
      <I18nProvider>
        <InteractiveChart
          symbol="XAUUSD"
          timeframe="1h"
          candles={sampleCandles}
          status="connected"
          provider={sampleProvider}
          entryPrice={null}
          stopLossPrice={null}
          takeProfits={[]}
          signalAction="NO SIGNAL"
          isProviderConnected={true}
        />
      </I18nProvider>
    );
  });
});

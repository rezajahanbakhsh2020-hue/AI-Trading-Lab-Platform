import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { SignalCard } from "./SignalCard";
import { createHostSnapshotFromProject1, PROJECT1_GATEWAY_PORT } from "../../architecture/hostView";
import { I18nProvider } from "../../i18n";

const renderWithI18n = (ui: React.ReactNode) => {
  return render(<I18nProvider>{ui}</I18nProvider>);
};

describe("SignalCard UI Component", () => {
  beforeEach(() => {
    cleanup();
  });
  it("renders active BUY signal with trade setup levels and MTF metadata", () => {
    const nowSec = Date.now() / 1000;
    const snapshot = createHostSnapshotFromProject1(
      PROJECT1_GATEWAY_PORT,
      {
        signal_id: "sig_buy_001",
        symbol: "XAUUSD",
        signal_type: "buy",
        timestamp: nowSec - 10,
        entry_price: 2650.0,
        stop_loss: 2630.0,
        take_profits: [2680.0, 2700.0],
        confidence: 0.88,
        strategy_name: "GoldTrendv1",
        timeframe: "15m",
        metadata: {
          provenance_type: "live_signal",
          is_live: true,
          mtf: {
            star_representation: "⭐⭐⭐⭐⭐",
            alignment_coverage: 5,
            classification: "ALIGNED",
            signals: [{ timeframe: "15m", direction: "buy" }],
          },
        },
      },
      "XAUUSD",
      "15m"
    );

    renderWithI18n(<SignalCard snapshot={snapshot} />);

    expect(screen.getByText("BUY")).toBeDefined();
    expect(screen.getByText("GoldTrendv1")).toBeDefined();
    expect(screen.getByText("2650")).toBeDefined();
    expect(screen.getByText("2630")).toBeDefined();
    expect(screen.getByText("2680")).toBeDefined();
    expect(screen.getByText("⭐⭐⭐⭐⭐")).toBeDefined();
    expect(screen.getByText("ALIGNED")).toBeDefined();
  });

  it("renders active NO_TRADE signal without fake levels and with notice message", () => {
    const nowSec = Date.now() / 1000;
    const snapshot = createHostSnapshotFromProject1(
      PROJECT1_GATEWAY_PORT,
      {
        signal_id: "sig_nt_001",
        symbol: "XAUUSD",
        signal_type: "no-trade",
        timestamp: nowSec - 10,
        entry_price: null,
        stop_loss: null,
        take_profits: [],
        confidence: null,
        strategy_name: "P1MTFStrategy",
        timeframe: "5m",
        metadata: {
          provenance_type: "live_signal",
          is_live: true,
          mtf: {
            star_representation: "⭐⭐☆☆☆",
            alignment_coverage: 2,
            classification: "NEUTRAL",
          },
        },
      },
      "XAUUSD",
      "5m"
    );

    renderWithI18n(<SignalCard snapshot={snapshot} />);

    expect(screen.getAllByText("NO TRADE").length).toBeGreaterThan(0);
    expect(screen.getByText("P1MTFStrategy")).toBeDefined();
    expect(screen.getByText("⭐⭐☆☆☆")).toBeDefined();
    expect(screen.getByText("NEUTRAL")).toBeDefined();

    // Verify Entry / SL levels are NOT displayed
    expect(screen.queryByText("2650")).toBeNull();
  });

  it("renders NO CURRENT SIGNAL for absent live record", () => {
    const snapshot = createHostSnapshotFromProject1(
      PROJECT1_GATEWAY_PORT,
      null,
      "XAUUSD",
      "1h"
    );

    renderWithI18n(<SignalCard snapshot={snapshot} />);

    expect(screen.getByText("NO CURRENT SIGNAL")).toBeDefined();
    expect(screen.getByText(/No active current live signal emitted by Project 1/i)).toBeDefined();
  });

  it("triggers onSelectTimeframe when clicking timeframe buttons on SignalCard", () => {
    const snapshot = createHostSnapshotFromProject1(
      PROJECT1_GATEWAY_PORT,
      null,
      "XAUUSD",
      "1h"
    );

    const onSelectTf = vi.fn();
    renderWithI18n(<SignalCard snapshot={snapshot} onSelectTimeframe={onSelectTf} />);

    expect(screen.queryByRole("button", { name: "1m" })).toBeNull();
    for (const tf of ["5m", "15m", "30m", "1H", "4H", "1D"]) {
      expect(screen.getByRole("button", { name: tf })).toBeDefined();
    }
    const tf5mBtn = screen.getByRole("button", { name: "5m" });
    fireEvent.click(tf5mBtn);

    expect(onSelectTf).toHaveBeenCalledWith("5m");
  });
});

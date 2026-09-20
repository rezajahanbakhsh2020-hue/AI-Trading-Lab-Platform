import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PerformanceViewer } from "./PerformanceViewer";
import { createDisconnectedHostSnapshot } from "../../architecture/hostView";
import { I18nProvider } from "../../i18n";

describe("PerformanceViewer", () => {
  it("renders disconnected empty state when Project 1 is disconnected", () => {
    const snapshot = createDisconnectedHostSnapshot("XAUUSD", "1h");
    render(
      <I18nProvider>
        <PerformanceViewer snapshot={snapshot} />
      </I18nProvider>
    );

    expect(screen.getByTestId("performance-viewer")).toBeDefined();
    expect(screen.getAllByText(/DISCONNECTED/i)[0]).toBeDefined();
  });

  it("renders active performance analytics summary when data exists", () => {
    const snapshot = {
      project1: { connected: true, status: "connected" },
      performance: {
        status: "active",
        message: "Performance analytics evaluated.",
        data: {
          strategy_name: "GoldTrendv1",
          symbol: "XAUUSD",
          timeframe: "1h",
          status: "active",
          total_trades: 124,
          win_rate: 0.645,
          profit_factor: 2.15,
          max_drawdown: 0.085,
          net_profit: 14250.0,
          sharpe_ratio_estimate: 1.39,
          drawdown_profile: {
            max_drawdown_pct: 0.085,
            recovery_factor: 16.76,
            risk_classification: "LOW",
          },
          risk_profile: {
            reward_to_risk_expectancy: 2.15,
            max_drawdown: 0.085,
            win_loss_ratio: 1.82,
            risk_level: "low",
            position_risk_pass: true,
            drawdown_limit_pass: true,
            risk_assessment_status: "compliant",
          },
          walk_forward_efficiency: 0.91,
          walk_forward_consistency: 0.88,
          detail: "Backtest assessment evaluated.",
        },
      },
    } as any;

    render(
      <I18nProvider>
        <PerformanceViewer snapshot={snapshot} />
      </I18nProvider>
    );

    expect(screen.getAllByTestId("performance-viewer")[0]).toBeDefined();
    expect(screen.getByText("124")).toBeDefined();
    expect(screen.getByText("LOW RISK")).toBeDefined();
  });
});

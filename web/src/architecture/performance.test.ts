import { describe, it, expect } from "vitest";
import { extractPerformanceAnalytics } from "./performance";
import { createDisconnectedHostSnapshot } from "./hostView";

describe("extractPerformanceAnalytics", () => {
  it("extracts disconnected state when Project 1 is disconnected", () => {
    const snapshot = createDisconnectedHostSnapshot("XAUUSD", "1h");
    const state = extractPerformanceAnalytics(snapshot);

    expect(state.status).toBe("disconnected");
    expect(state.summary).toBeNull();
    expect(state.message).toContain("disconnected");
  });

  it("extracts active performance analytics data when present", () => {
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

    const state = extractPerformanceAnalytics(snapshot);

    expect(state.status).toBe("active");
    expect(state.summary).not.toBeNull();
    expect(state.summary?.strategy_name).toBe("GoldTrendv1");
    expect(state.summary?.win_rate).toBe(0.645);
    expect(state.summary?.drawdown_profile?.risk_classification).toBe("LOW");
    expect(state.summary?.risk_profile?.risk_assessment_status).toBe("compliant");
  });

  it("extracts unauthorized state when performance access is restricted", () => {
    const snapshot = {
      project1: { connected: true, status: "connected" },
      performance: {
        status: "unauthorized",
        message: "Access denied: performance analytics restricted.",
      },
    } as any;

    const state = extractPerformanceAnalytics(snapshot);

    expect(state.status).toBe("unauthorized");
    expect(state.summary).toBeNull();
    expect(state.message).toContain("Access denied");
  });

  it("extracts empty state when no performance data exists", () => {
    const snapshot = {
      project1: { connected: true, status: "connected" },
      performance: {
        status: "empty",
        message: "No performance data available for this market context.",
      },
    } as any;

    const state = extractPerformanceAnalytics(snapshot);

    expect(state.status).toBe("empty");
    expect(state.summary).toBeNull();
  });
});

import type { HostSnapshot } from "./hostView";

export interface DrawdownProfileData {
  max_drawdown_pct: number;
  recovery_factor: number;
  risk_classification: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | string;
}

export interface RiskAnalyticsProfileData {
  reward_to_risk_expectancy: number;
  max_drawdown: number;
  win_loss_ratio: number;
  risk_level: string;
  position_risk_pass: boolean;
  drawdown_limit_pass: boolean;
  risk_assessment_status: "compliant" | "degraded" | "breached" | string;
}

export interface StrategyPerformanceSummaryData {
  strategy_name: string;
  symbol: string;
  timeframe: string;
  status: string;
  total_trades: number;
  win_rate: number;
  profit_factor: number;
  max_drawdown: number;
  net_profit: number;
  sharpe_ratio_estimate?: number | null;
  drawdown_profile?: DrawdownProfileData | null;
  risk_profile?: RiskAnalyticsProfileData | null;
  walk_forward_efficiency?: number | null;
  walk_forward_consistency?: number | null;
  detail?: string | null;
}

export interface PerformanceAnalyticsState {
  status: "active" | "connected" | "disconnected" | "unavailable" | "empty" | "unauthorized" | "failed" | "loading";
  message: string;
  summary: StrategyPerformanceSummaryData | null;
}

export function extractPerformanceAnalytics(snapshot: HostSnapshot): PerformanceAnalyticsState {
  if (!snapshot.project1.connected) {
    return {
      status: "disconnected",
      message: "Project 1 is disconnected. Connect Project 1 to access strategy performance analytics.",
      summary: null,
    };
  }

  const perf = snapshot.performance as {
    status?: string;
    message?: string;
    data?: StrategyPerformanceSummaryData;
  };

  if (!perf) {
    return {
      status: "unavailable",
      message: "Performance analytics are unavailable until Project 1 outputs are evaluated.",
      summary: null,
    };
  }

  const statusStr = (perf.status || "unavailable").toLowerCase() as PerformanceAnalyticsState["status"];

  if (statusStr === "unauthorized") {
    return {
      status: "unauthorized",
      message: perf.message || "Access denied: performance analytics restricted.",
      summary: null,
    };
  }

  if (statusStr === "empty") {
    return {
      status: "empty",
      message: perf.message || "No performance data available for this market context.",
      summary: null,
    };
  }

  if (statusStr === "failed") {
    return {
      status: "failed",
      message: perf.message || "Performance analytics calculation encountered an exception.",
      summary: null,
    };
  }

  if (!perf.data) {
    return {
      status: "unavailable",
      message: perf.message || "Performance analytics are unavailable until Project 1 outputs are evaluated.",
      summary: null,
    };
  }

  return {
    status: statusStr === "active" ? "active" : "connected",
    message: perf.message || "Authentic strategy performance analytics evaluated.",
    summary: perf.data,
  };
}

/* Authenticated REST API Client Helpers */

export async function fetchPerformanceSummary(
  token: string | null,
  strategyName: string = "Project 1 Strategy",
  symbol: string = "XAUUSD",
  timeframe: string = "1h"
): Promise<{ success: boolean; performance?: StrategyPerformanceSummaryData; error?: string }> {
  try {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const url = `/api/v1/performance/summary?strategy_name=${encodeURIComponent(strategyName)}&symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`;
    const res = await fetch(url, { method: "GET", headers });
    const data = await res.json();

    if (res.ok && data.success) {
      return { success: true, performance: data.performance?.data || data.performance };
    }
    return { success: false, error: data.why || data.message || "Failed to fetch performance summary" };
  } catch (err: any) {
    return { success: false, error: err.message || "Network error fetching performance summary" };
  }
}

export async function fetchRiskProfile(
  token: string | null,
  strategyName: string = "Project 1 Strategy",
  symbol: string = "XAUUSD",
  timeframe: string = "1h"
): Promise<{ success: boolean; risk?: RiskAnalyticsProfileData; drawdown?: DrawdownProfileData; error?: string }> {
  try {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const url = `/api/v1/performance/risk?strategy_name=${encodeURIComponent(strategyName)}&symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`;
    const res = await fetch(url, { method: "GET", headers });
    const data = await res.json();

    if (res.ok && data.success) {
      return { success: true, risk: data.risk, drawdown: data.drawdown };
    }
    return { success: false, error: data.why || data.message || "Failed to fetch risk profile" };
  } catch (err: any) {
    return { success: false, error: err.message || "Network error fetching risk profile" };
  }
}

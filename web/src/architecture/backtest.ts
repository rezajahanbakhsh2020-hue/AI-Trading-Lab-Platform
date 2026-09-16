import type { HostSnapshot } from "./hostView";

export interface BacktestMetrics {
  totalTrades: number;
  winRate: number;
  profitFactor: number;
  maxDrawdown: number;
  netProfit: number;
}

export interface StabilityInfo {
  score: number;
  riskLevel: "low" | "medium" | "high" | "critical";
  metrics?: Record<string, unknown>;
}

export interface BacktestData {
  strategyName: string;
  symbol: string;
  timeframe: string;
  totalTrades: number;
  winRate: number;
  profitFactor: number;
  maxDrawdown: number;
  netProfit: number;
  stability?: StabilityInfo | null;
  detail?: string | null;
}

export interface BacktestState {
  status: "available" | "unavailable" | "loading" | "error" | "disconnected";
  message: string;
  data: BacktestData | null;
}

export function extractBacktestState(snapshot: HostSnapshot): BacktestState {
  if (!snapshot.project1.connected) {
    return {
      status: "disconnected",
      message: "No Project 1 data connected. Connect Project 1 to access backtest assessment.",
      data: null,
    };
  }

  const perf = snapshot.performance as {
    status?: string;
    message?: string;
    data?: Record<string, any>;
  };

  if (!perf || perf.status === "unavailable" || !perf.data) {
    return {
      status: "unavailable",
      message: perf?.message || "Backtest results are unavailable until a strategy assessment is executed.",
      data: null,
    };
  }

  const raw = perf.data;
  const stabilityRaw = raw.stability as Record<string, any> | undefined;

  const data: BacktestData = {
    strategyName: raw.strategy_name || snapshot.strategy.name || "Project 1 Strategy",
    symbol: raw.symbol || snapshot.market.symbol || "XAUUSD",
    timeframe: raw.timeframe || snapshot.market.timeframe || "1h",
    totalTrades: Number(raw.total_trades ?? 0),
    winRate: Number(raw.win_rate ?? 0),
    profitFactor: Number(raw.profit_factor ?? 0),
    maxDrawdown: Number(raw.max_drawdown ?? 0),
    netProfit: Number(raw.net_profit ?? 0),
    stability: stabilityRaw
      ? {
          score: Number(stabilityRaw.score ?? 0),
          riskLevel: (stabilityRaw.risk_level || "medium") as any,
          metrics: stabilityRaw.metrics || {},
        }
      : null,
    detail: raw.detail || null,
  };

  return {
    status: "available",
    message: perf.message || "Backtest assessment calculated on observed market candles.",
    data,
  };
}

export const SAMPLE_BACKTEST_DATA: BacktestData = {
  strategyName: "GoldTrendv1",
  symbol: "XAUUSD",
  timeframe: "1h",
  totalTrades: 124,
  winRate: 0.645,
  profitFactor: 2.15,
  maxDrawdown: 0.085,
  netProfit: 14250.0,
  stability: {
    score: 0.82,
    riskLevel: "low",
    metrics: {
      win_rate: 0.645,
      profit_factor: 2.15,
      max_drawdown: 0.085,
      net_profit: 14250.0,
      total_trades: 124,
    },
  },
  detail: "Backtest assessment completed successfully on historical candles.",
};

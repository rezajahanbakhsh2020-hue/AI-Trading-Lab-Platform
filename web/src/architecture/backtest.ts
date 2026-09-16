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

export interface WalkForwardWindowData {
  windowIndex: number;
  inSampleTrades: number;
  inSampleWinRate: number;
  inSampleProfitFactor: number;
  outOfSampleTrades: number;
  outOfSampleWinRate: number;
  outOfSampleProfitFactor: number;
  outOfSampleMaxDrawdown: number;
  outOfSampleNetProfit: number;
  efficiencyRatio: number;
}

export interface WalkForwardData {
  strategyName: string;
  symbol: string;
  timeframe: string;
  windows: WalkForwardWindowData[];
  overallOutOfSampleWinRate: number;
  overallOutOfSampleProfitFactor: number;
  overallOutOfSampleMaxDrawdown: number;
  overallOutOfSampleNetProfit: number;
  stability?: StabilityInfo | null;
  detail?: string | null;
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
  walkForward?: WalkForwardData | null;
  detail?: string | null;
}

export interface BacktestState {
  status: "available" | "unavailable" | "loading" | "error" | "disconnected" | "empty" | "invalid" | "failed" | "unauthorized";
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

  if (!perf) {
    return {
      status: "unavailable",
      message: "Backtest results are unavailable until a strategy assessment is executed.",
      data: null,
    };
  }

  const statusStr = (perf.status || "unavailable").toLowerCase();

  if (statusStr === "unauthorized") {
    return {
      status: "unauthorized",
      message: perf.message || "Access denied: backtest assessment restricted.",
      data: null,
    };
  }

  if (statusStr === "empty") {
    return {
      status: "empty",
      message: perf.message || "No market candles available for backtest execution.",
      data: null,
    };
  }

  if (statusStr === "invalid") {
    return {
      status: "invalid",
      message: perf.message || "Backtest parameters or raw result structure invalid.",
      data: null,
    };
  }

  if (statusStr === "failed" || statusStr === "error") {
    return {
      status: "failed",
      message: perf.message || "Backtest execution engine encountered an application failure.",
      data: null,
    };
  }

  if (statusStr === "unavailable" || !perf.data) {
    return {
      status: "unavailable",
      message: perf.message || "Backtest results are unavailable until a strategy assessment is executed.",
      data: null,
    };
  }

  const raw = perf.data;
  const stabilityRaw = raw.stability as Record<string, any> | undefined;

  const wfRaw = raw.walk_forward as Record<string, any> | undefined;
  let walkForwardData: WalkForwardData | null = null;

  if (wfRaw) {
    const rawWindows = (wfRaw.windows || []) as Record<string, any>[];
    const windows: WalkForwardWindowData[] = rawWindows.map((rw) => ({
      windowIndex: Number(rw.window_index ?? 0),
      inSampleTrades: Number(rw.in_sample_trades ?? 0),
      inSampleWinRate: Number(rw.in_sample_win_rate ?? 0),
      inSampleProfitFactor: Number(rw.in_sample_profit_factor ?? 0),
      outOfSampleTrades: Number(rw.out_of_sample_trades ?? 0),
      outOfSampleWinRate: Number(rw.out_of_sample_win_rate ?? 0),
      outOfSampleProfitFactor: Number(rw.out_of_sample_profit_factor ?? 0),
      outOfSampleMaxDrawdown: Number(rw.out_of_sample_max_drawdown ?? 0),
      outOfSampleNetProfit: Number(rw.out_of_sample_net_profit ?? 0),
      efficiencyRatio: Number(rw.efficiency_ratio ?? 1),
    }));

    const wfStabRaw = wfRaw.stability as Record<string, any> | undefined;

    walkForwardData = {
      strategyName: wfRaw.strategy_name || raw.strategy_name || "Project 1 Strategy",
      symbol: wfRaw.symbol || raw.symbol || "XAUUSD",
      timeframe: wfRaw.timeframe || raw.timeframe || "1h",
      windows,
      overallOutOfSampleWinRate: Number(wfRaw.overall_out_of_sample_win_rate ?? 0),
      overallOutOfSampleProfitFactor: Number(wfRaw.overall_out_of_sample_profit_factor ?? 0),
      overallOutOfSampleMaxDrawdown: Number(wfRaw.overall_out_of_sample_max_drawdown ?? 0),
      overallOutOfSampleNetProfit: Number(wfRaw.overall_out_of_sample_net_profit ?? 0),
      stability: wfStabRaw
        ? {
            score: Number(wfStabRaw.score ?? 0),
            riskLevel: (wfStabRaw.risk_level || "medium") as any,
            metrics: wfStabRaw.metrics || {},
          }
        : null,
      detail: wfRaw.detail || null,
    };
  }

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
    walkForward: walkForwardData,
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
  walkForward: {
    strategyName: "GoldTrendv1",
    symbol: "XAUUSD",
    timeframe: "1h",
    windows: [
      {
        windowIndex: 1,
        inSampleTrades: 40,
        inSampleWinRate: 0.68,
        inSampleProfitFactor: 2.3,
        outOfSampleTrades: 15,
        outOfSampleWinRate: 0.60,
        outOfSampleProfitFactor: 1.9,
        outOfSampleMaxDrawdown: 0.07,
        outOfSampleNetProfit: 3200.0,
        efficiencyRatio: 0.88,
      },
      {
        windowIndex: 2,
        inSampleTrades: 42,
        inSampleWinRate: 0.65,
        inSampleProfitFactor: 2.1,
        outOfSampleTrades: 18,
        outOfSampleWinRate: 0.61,
        outOfSampleProfitFactor: 2.0,
        outOfSampleMaxDrawdown: 0.08,
        outOfSampleNetProfit: 4100.0,
        efficiencyRatio: 0.94,
      },
      {
        windowIndex: 3,
        inSampleTrades: 45,
        inSampleWinRate: 0.63,
        inSampleProfitFactor: 2.0,
        outOfSampleTrades: 20,
        outOfSampleWinRate: 0.58,
        outOfSampleProfitFactor: 1.8,
        outOfSampleMaxDrawdown: 0.09,
        outOfSampleNetProfit: 3850.0,
        efficiencyRatio: 0.92,
      },
    ],
    overallOutOfSampleWinRate: 0.596,
    overallOutOfSampleProfitFactor: 1.89,
    overallOutOfSampleMaxDrawdown: 0.08,
    overallOutOfSampleNetProfit: 11150.0,
    stability: {
      score: 0.80,
      riskLevel: "low",
      metrics: {
        out_of_sample_win_rate: 0.596,
        out_of_sample_profit_factor: 1.89,
      },
    },
    detail: "Walk-forward validation executed across 3 sequential rolling windows.",
  },
  detail: "Backtest assessment completed successfully on historical candles.",
};

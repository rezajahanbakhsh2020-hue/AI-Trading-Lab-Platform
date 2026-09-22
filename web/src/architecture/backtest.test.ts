import { describe, it, expect } from "vitest";
import {
  extractBacktestState,
  SAMPLE_BACKTEST_DATA,
} from "./backtest";
import {
  createDisconnectedHostSnapshot,
  createHostSnapshotFromProject1,
} from "./hostView";
import {
  SAMPLE_CONNECTED_PORT,
  SAMPLE_REAL_PROJECT1_SIGNAL,
} from "./testFixtures";

describe("backtest architecture", () => {
  it("extracts disconnected state when project 1 is disconnected", () => {
    const snapshot = createDisconnectedHostSnapshot();
    const state = extractBacktestState(snapshot);

    expect(state.status).toBe("disconnected");
    expect(state.data).toBeNull();
  });

  it("extracts unavailable state when performance data is missing", () => {
    const snapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL
    );
    const state = extractBacktestState(snapshot);

    expect(state.status).toBe("unavailable");
    expect(state.data).toBeNull();
  });

  it("extracts empty, invalid, unauthorized, and failed states correctly", () => {
    const snapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL
    );

    snapshot.performance = { status: "empty", message: "no candles available", data: {} } as any;
    expect(extractBacktestState(snapshot).status).toBe("empty");

    snapshot.performance = { status: "invalid", message: "invalid parameters", data: {} } as any;
    expect(extractBacktestState(snapshot).status).toBe("invalid");

    snapshot.performance = { status: "unauthorized", message: "access denied", data: {} } as any;
    expect(extractBacktestState(snapshot).status).toBe("unauthorized");

    snapshot.performance = { status: "failed", message: "execution exception", data: {} } as any;
    expect(extractBacktestState(snapshot).status).toBe("failed");
  });

  it("extracts available state when performance assessment data exists", () => {
    const snapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL
    );
    snapshot.performance = {
      status: "available",
      message: "Backtest calculated.",
      data: {
        strategy_name: "GoldTrendv1",
        symbol: "XAUUSD",
        timeframe: "1h",
        total_trades: 120,
        win_rate: 0.65,
        profit_factor: 2.1,
        max_drawdown: 0.08,
        net_profit: 15000,
        stability: {
          score: 0.85,
          risk_level: "low",
        },
      },
    } as any;

    const state = extractBacktestState(snapshot);

    expect(state.status).toBe("available");
    expect(state.data).not.toBeNull();
    expect(state.data?.strategyName).toBe("GoldTrendv1");
    expect(state.data?.totalTrades).toBe(120);
    expect(state.data?.winRate).toBe(0.65);
    expect(state.data?.stability?.score).toBe(0.85);
  });

  it("sample backtest data contains complete metrics", () => {
    expect(SAMPLE_BACKTEST_DATA.strategyName).toBe("GoldTrendv1");
    expect(SAMPLE_BACKTEST_DATA.winRate).toBe(0.645);
    expect(SAMPLE_BACKTEST_DATA.stability?.riskLevel).toBe("low");
  });
});

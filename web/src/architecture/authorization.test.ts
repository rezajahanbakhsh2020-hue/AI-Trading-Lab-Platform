import { describe, it, expect } from "vitest";
import {
  extractAutonomousAuthorization,
} from "./authorization";
import { createDisconnectedHostSnapshot } from "./hostView";

describe("Autonomous Authorization State Extraction", () => {
  it("returns DISCONNECTED_AUTHORIZATION when disconnected", () => {
    const snapshot = createDisconnectedHostSnapshot("XAUUSD", "1h");
    const auth = extractAutonomousAuthorization(snapshot);
    expect(auth.status).toBe("DISCONNECTED");
    expect(auth.isAuthorized).toBe(false);
    expect(auth.checks.length).toBe(0);
  });

  it("extracts authorization payload from snapshot correctly when active", () => {
    const mockSnapshot: any = {
      project1: { connected: true },
      authorization: {
        status: "AUTHORIZED",
        isAuthorized: true,
        reason: "All gates passed.",
        checks: [
          {
            id: "signal_tradable",
            label: "Signal Tradability Gate",
            passed: true,
            reason: "Signal is BUY",
          },
          {
            id: "risk_reward",
            label: "Risk / Reward Threshold",
            passed: true,
            reason: "R:R ratio is 2.50:1",
          },
        ],
        riskRewardRatio: 2.5,
        timestamp: 1700000000,
      },
    };

    const auth = extractAutonomousAuthorization(mockSnapshot);
    expect(auth.status).toBe("AUTHORIZED");
    expect(auth.isAuthorized).toBe(true);
    expect(auth.checks.length).toBe(2);
    expect(auth.checks[0].passed).toBe(true);
    expect(auth.riskRewardRatio).toBe(2.5);
  });

  it("returns fallback state when authorization is missing on connected snapshot", () => {
    const mockSnapshot: any = {
      project1: { connected: true },
      signal: { action: "NO SIGNAL" },
    };

    const auth = extractAutonomousAuthorization(mockSnapshot);
    expect(auth.status).toBe("NO_SIGNAL");
    expect(auth.isAuthorized).toBe(false);
  });
});

import type { HostSnapshot } from "./hostView";

export interface ExecutionGateCheck {
  id: string;
  label: string;
  passed: boolean;
  reason: string;
}

export interface AutonomousAuthorizationState {
  status: "AUTHORIZED" | "UNAUTHORIZED" | "NO_SIGNAL" | "DISCONNECTED" | "REJECTED" | string;
  isAuthorized: boolean;
  reason: string;
  checks: readonly ExecutionGateCheck[];
  riskRewardRatio: number | null;
  timestamp: number | null;
}

export const DISCONNECTED_AUTHORIZATION: AutonomousAuthorizationState = {
  status: "DISCONNECTED",
  isAuthorized: false,
  reason: "Project 1 is disconnected. Connect Project 1 to enable autonomous execution evaluation.",
  checks: [],
  riskRewardRatio: null,
  timestamp: null,
};

export const NO_SIGNAL_AUTHORIZATION: AutonomousAuthorizationState = {
  status: "NO_SIGNAL",
  isAuthorized: false,
  reason: "No active signal emitted by Project 1. Autonomous execution holds on NO SIGNAL.",
  checks: [
    {
      id: "signal_tradable",
      label: "Signal Tradability Gate",
      passed: false,
      reason: "Signal action is NO SIGNAL / HOLD",
    },
  ],
  riskRewardRatio: null,
  timestamp: null,
};

/**
 * Extracts autonomous execution authorization payload from HostSnapshot safely.
 */
export function extractAutonomousAuthorization(snapshot: HostSnapshot): AutonomousAuthorizationState {
  if (!snapshot || !snapshot.project1 || !snapshot.project1.connected) {
    return DISCONNECTED_AUTHORIZATION;
  }

  const rawAuth = (snapshot as any).authorization;
  if (!rawAuth) {
    if (snapshot.signal && snapshot.signal.action === "NO SIGNAL") {
      return NO_SIGNAL_AUTHORIZATION;
    }
    return {
      status: "UNAUTHORIZED",
      isAuthorized: false,
      reason: "Autonomous authorization evaluation unavailable in snapshot.",
      checks: [],
      riskRewardRatio: null,
      timestamp: null,
    };
  }

  return {
    status: rawAuth.status ?? "UNAUTHORIZED",
    isAuthorized: Boolean(rawAuth.isAuthorized),
    reason: rawAuth.reason ?? "Evaluation status pending.",
    checks: Array.isArray(rawAuth.checks)
      ? rawAuth.checks.map((c: any) => ({
          id: String(c.id || "check"),
          label: String(c.label || "Gate Check"),
          passed: Boolean(c.passed),
          reason: String(c.reason || ""),
        }))
      : [],
    riskRewardRatio: typeof rawAuth.riskRewardRatio === "number" ? rawAuth.riskRewardRatio : null,
    timestamp: typeof rawAuth.timestamp === "number" ? rawAuth.timestamp : null,
  };
}

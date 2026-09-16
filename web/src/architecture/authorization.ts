import type { HostSnapshot } from "./hostView";

export type AuthorizationStatus = "AUTHORIZED" | "REJECTED" | "DISCONNECTED";

export interface AuthorizationCheck {
  id: string;
  label: string;
  passed: boolean;
  reason: string;
}

export interface AutonomousAuthorizationPayload {
  status: AuthorizationStatus;
  isAuthorized: boolean;
  reason: string;
  checks: readonly AuthorizationCheck[];
  riskRewardRatio: number | null;
  timestamp: number | null;
}

/**
 * Extract autonomous authorization payload from a HostSnapshot cleanly.
 */
export function extractAuthorizationFromSnapshot(
  snapshot: HostSnapshot
): AutonomousAuthorizationPayload {
  if (snapshot.authorization) {
    return snapshot.authorization;
  }

  // Fallback if missing
  return {
    status: snapshot.project1.connected ? "REJECTED" : "DISCONNECTED",
    isAuthorized: false,
    reason: snapshot.project1.connected
      ? "No active trade setup available for autonomous authorization."
      : "Project 1 is disconnected. Connect Project 1 to enable autonomous execution evaluation.",
    checks: [],
    riskRewardRatio: null,
    timestamp: null,
  };
}

/**
 * Return human badge CSS class and status label key.
 */
export function getAuthorizationStatusBadge(status: AuthorizationStatus): {
  badgeClass: string;
  labelKey: string;
} {
  switch (status) {
    case "AUTHORIZED":
      return { badgeClass: "ready-chip", labelKey: "authorization.statusAuthorized" };
    case "REJECTED":
      return { badgeClass: "warn-chip", labelKey: "authorization.statusRejected" };
    case "DISCONNECTED":
    default:
      return { badgeClass: "", labelKey: "authorization.statusDisconnected" };
  }
}

/**
 * Compute summary stats for authorization gate checks.
 */
export function summarizeAuthorizationChecks(checks: readonly AuthorizationCheck[]): {
  total: number;
  passedCount: number;
  failedCount: number;
  passPercentage: number;
} {
  const total = checks.length;
  if (total === 0) {
    return { total: 0, passedCount: 0, failedCount: 0, passPercentage: 0 };
  }

  const passedCount = checks.filter((c) => c.passed).length;
  const failedCount = total - passedCount;
  const passPercentage = Math.round((passedCount / total) * 100);

  return {
    total,
    passedCount,
    failedCount,
    passPercentage,
  };
}

import { describe, expect, it } from "vitest";
import {
  extractAuthorizationFromSnapshot,
  getAuthorizationStatusBadge,
  summarizeAuthorizationChecks,
  type AuthorizationCheck,
} from "./authorization";
import {
  createDisconnectedHostSnapshot,
  createHostSnapshotFromProject1,
  SAMPLE_CONNECTED_PORT,
  SAMPLE_REAL_PROJECT1_SIGNAL,
} from "./hostView";

describe("Autonomous Authorization Architecture", () => {
  it("extracts authorization payload from disconnected snapshot", () => {
    const snapshot = createDisconnectedHostSnapshot();
    const auth = extractAuthorizationFromSnapshot(snapshot);

    expect(auth.status).toBe("DISCONNECTED");
    expect(auth.isAuthorized).toBe(false);
    expect(auth.checks.length).toBe(4);
    expect(auth.checks.every((c) => !c.passed)).toBe(true);
  });

  it("extracts authorization payload from connected Project 1 snapshot emitting valid BUY signal", () => {
    const snapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL,
      "XAUUSD",
      "1h"
    );
    const auth = extractAuthorizationFromSnapshot(snapshot);

    expect(auth.status).toBe("AUTHORIZED");
    expect(auth.isAuthorized).toBe(true);
    expect(auth.checks.length).toBe(4);
    expect(auth.checks.every((c) => c.passed)).toBe(true);
    expect(auth.riskRewardRatio).toBeGreaterThanOrEqual(1.0);
  });

  it("returns proper badge classes and translation keys", () => {
    expect(getAuthorizationStatusBadge("AUTHORIZED")).toEqual({
      badgeClass: "ready-chip",
      labelKey: "authorization.statusAuthorized",
    });
    expect(getAuthorizationStatusBadge("REJECTED")).toEqual({
      badgeClass: "warn-chip",
      labelKey: "authorization.statusRejected",
    });
    expect(getAuthorizationStatusBadge("DISCONNECTED")).toEqual({
      badgeClass: "",
      labelKey: "authorization.statusDisconnected",
    });
  });

  it("summarizes gate check statistics accurately", () => {
    const checks: AuthorizationCheck[] = [
      { id: "c1", label: "Gate 1", passed: true, reason: "Passed" },
      { id: "c2", label: "Gate 2", passed: true, reason: "Passed" },
      { id: "c3", label: "Gate 3", passed: false, reason: "Failed" },
      { id: "c4", label: "Gate 4", passed: true, reason: "Passed" },
    ];

    const summary = summarizeAuthorizationChecks(checks);
    expect(summary.total).toBe(4);
    expect(summary.passedCount).toBe(3);
    expect(summary.failedCount).toBe(1);
    expect(summary.passPercentage).toBe(75);
  });

  it("redacts protected level details for non-admin users without read:trade_setups permission", () => {
    const nonAdminUser = {
      userId: "user_regular",
      role: "user" as const,
      permissions: ["read:signals"] as const,
      isAdmin: false,
    };

    const snapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL,
      "XAUUSD",
      "1h",
      {},
      nonAdminUser
    );

    const levelSanityCheck = snapshot.authorization.checks.find((c) => c.id === "level_sanity");
    expect(levelSanityCheck?.reason).toBe("Restricted to authorized users.");
  });
});

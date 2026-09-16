import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { I18nProvider } from "../../i18n";
import {
  createDisconnectedHostSnapshot,
  createHostSnapshotFromProject1,
  SAMPLE_CONNECTED_PORT,
  SAMPLE_REAL_PROJECT1_SIGNAL,
} from "../../architecture/hostView";
import { AutonomousAuthorizationViewer } from "./AutonomousAuthorizationViewer";

describe("AutonomousAuthorizationViewer Component", () => {
  it("renders authorized state when Project 1 emits tradable BUY signal", () => {
    const snapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL,
      "XAUUSD",
      "1h"
    );

    render(
      <I18nProvider>
        <AutonomousAuthorizationViewer snapshot={snapshot} />
      </I18nProvider>
    );

    expect(screen.getByText("Autonomous Execution Authorization")).toBeDefined();
    expect(screen.getAllByText("AUTHORIZED").length).toBeGreaterThan(0);
    expect(screen.getByText("autonomous execution authorized")).toBeDefined();
    expect(screen.getByText("Signal Tradability Gate")).toBeDefined();
    expect(screen.getByText("Readiness & Stability Gate")).toBeDefined();
    expect(screen.getByText("Trade Setup Level Geometry")).toBeDefined();
    expect(screen.getByText("Risk / Reward Threshold")).toBeDefined();
  });

  it("renders disconnected state when Project 1 is disconnected", () => {
    const snapshot = createDisconnectedHostSnapshot();

    render(
      <I18nProvider>
        <AutonomousAuthorizationViewer snapshot={snapshot} />
      </I18nProvider>
    );

    expect(screen.getAllByText("DISCONNECTED").length).toBeGreaterThan(0);
    expect(
      screen.getByText(
        "Project 1 is disconnected. Connect Project 1 to enable autonomous execution evaluation."
      )
    ).toBeDefined();
  });

  it("renders security boundary notice for standard user role", () => {
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

    render(
      <I18nProvider>
        <AutonomousAuthorizationViewer snapshot={snapshot} />
      </I18nProvider>
    );

    expect(
      screen.getAllByText(
        "Standard user role active. Security Boundary Service redacts proprietary level geometry reasons for unauthorized roles to prevent indicator reverse engineering."
      ).length
    ).toBeGreaterThan(0);
  });
});

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { AutonomousAuthorizationViewer } from "./AutonomousAuthorizationViewer";
import { createDisconnectedHostSnapshot } from "../../architecture/hostView";
import { I18nProvider } from "../../i18n";

describe("AutonomousAuthorizationViewer Component", () => {
  it("renders disconnected state when Project 1 is disconnected", () => {
    const snapshot = createDisconnectedHostSnapshot("XAUUSD", "1h");
    render(
      <I18nProvider>
        <AutonomousAuthorizationViewer snapshot={snapshot} />
      </I18nProvider>
    );

    expect(screen.getByText("Authorization Decision")).toBeDefined();
    expect(screen.getByText("DISCONNECTED")).toBeDefined();
  });

  it("renders active authorization status and gate checks when connected", () => {
    const mockSnapshot: any = {
      project1: { connected: true },
      authorization: {
        status: "AUTHORIZED",
        isAuthorized: true,
        reason: "All autonomous execution gates passed.",
        checks: [
          {
            id: "signal_tradable",
            label: "Signal Tradability Gate",
            passed: true,
            reason: "Signal action is BUY",
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

    render(
      <I18nProvider>
        <AutonomousAuthorizationViewer snapshot={mockSnapshot} />
      </I18nProvider>
    );

    expect(screen.getByText("AUTHORIZED FOR EXECUTION")).toBeDefined();
    expect(screen.getByText("All autonomous execution gates passed.")).toBeDefined();
    expect(screen.getByText("Signal Tradability Gate")).toBeDefined();
    expect(screen.getByText("Risk / Reward Threshold")).toBeDefined();
    expect(screen.getAllByText("2.50 : 1").length).toBeGreaterThan(0);
  });
});

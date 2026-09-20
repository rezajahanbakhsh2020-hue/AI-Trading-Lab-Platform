import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RiskViewer } from "./RiskViewer";
import { createDisconnectedHostSnapshot } from "../../architecture/hostView";
import { I18nProvider } from "../../i18n";

describe("RiskViewer", () => {
  it("renders risk compliance and trade setup levels", () => {
    const snapshot = createDisconnectedHostSnapshot("XAUUSD", "1h");
    snapshot.risk = {
      entry: 2650.0,
      stopLoss: 2630.0,
      takeProfits: [2680.0, 2700.0, 2720.0],
      status: "available",
      message: "Real trade setup levels provided by Project 1.",
    };

    render(
      <I18nProvider>
        <RiskViewer snapshot={snapshot} />
      </I18nProvider>
    );

    expect(screen.getByTestId("risk-viewer")).toBeDefined();
    expect(screen.getByText("Risk Assessment Status")).toBeDefined();
  });
});

import { describe, it, expect } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { BacktestViewer } from "./BacktestViewer";
import {
  createDisconnectedHostSnapshot,
  createHostSnapshotFromProject1,
  SAMPLE_CONNECTED_PORT,
  SAMPLE_REAL_PROJECT1_SIGNAL,
} from "../../architecture/hostView";
import { I18nProvider } from "../../i18n";

describe("BacktestViewer component", () => {
  it("renders empty state when disconnected", () => {
    cleanup();
    const snapshot = createDisconnectedHostSnapshot();
    render(
      <I18nProvider>
        <BacktestViewer snapshot={snapshot} />
      </I18nProvider>
    );

    expect(screen.getByText(/DISCONNECTED/i)).toBeDefined();
  });

  it("toggles preview sample backtest data on button click", () => {
    cleanup();
    const snapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL
    );

    render(
      <I18nProvider>
        <BacktestViewer snapshot={snapshot} />
      </I18nProvider>
    );

    const toggleBtn = screen.getByRole("button");
    expect(toggleBtn).toBeDefined();

    fireEvent.click(toggleBtn);

    expect(screen.getByText("GoldTrendv1")).toBeDefined();
    expect(screen.getByText("124")).toBeDefined();
    expect(screen.getByText("2.15")).toBeDefined();
  });
});

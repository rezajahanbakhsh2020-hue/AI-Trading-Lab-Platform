import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, expect, it, vi, afterEach } from "vitest";
import { OrderIntentViewer } from "./OrderIntentViewer";
import { createHostSnapshotFromProject1, SAMPLE_CONNECTED_PORT, SAMPLE_REAL_PROJECT1_SIGNAL } from "../../architecture/hostView";
import { I18nProvider } from "../../i18n";

const snapshot = createHostSnapshotFromProject1(
  SAMPLE_CONNECTED_PORT,
  SAMPLE_REAL_PROJECT1_SIGNAL,
  "XAUUSD",
  "1h"
);

describe("OrderIntentViewer component", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders non-execution disclosure banner and staged intent cards", () => {
    render(
      <I18nProvider>
        <OrderIntentViewer snapshot={snapshot} />
      </I18nProvider>
    );

    expect(screen.getByText(/Non-Execution Disclosure/i)).not.toBeNull();
    expect(screen.getAllByText(/XAUUSD/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/BUY/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Cancel Intent/i).length).toBeGreaterThan(0);
  });

  it("filters order intents by symbol query", () => {
    render(
      <I18nProvider>
        <OrderIntentViewer snapshot={snapshot} />
      </I18nProvider>
    );

    const searchInput = screen.getByPlaceholderText(/Search intents by symbol/i);
    fireEvent.change(searchInput, { target: { value: "NON_EXISTENT_SYMBOL" } });

    expect(screen.getByText(/No Order Intents Found/i)).not.toBeNull();
  });

  it("handles cancel action on staged order intent", () => {
    const handleTransition = vi.fn();
    window.prompt = vi.fn().mockReturnValue("User requested cancellation");

    render(
      <I18nProvider>
        <OrderIntentViewer snapshot={snapshot} onTransitionIntent={handleTransition} />
      </I18nProvider>
    );

    const cancelButtons = screen.getAllByText("Cancel Intent");
    fireEvent.click(cancelButtons[0]);

    expect(handleTransition).toHaveBeenCalledWith(
      expect.stringContaining("ord_intent_"),
      "CANCELLED",
      "User requested cancellation"
    );
  });
});

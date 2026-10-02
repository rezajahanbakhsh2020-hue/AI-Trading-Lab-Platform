import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, expect, it, vi, afterEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { OrderIntentViewer } from "./OrderIntentViewer";
import { createHostSnapshotFromProject1 } from "../../architecture/hostView";
import { SAMPLE_CONNECTED_PORT, SAMPLE_REAL_PROJECT1_SIGNAL } from "../../architecture/testFixtures";
import { I18nProvider } from "../../i18n";

const sampleIntent = {
  order_intent_id: "ord_intent_p1_xauusd_1h_live_current",
  authorization_id: "auth_test",
  user_id: "user_test",
  symbol: "XAUUSD",
  direction: "buy" as const,
  order_type: "market" as const,
  requested_price: 2650.5,
  requested_quantity: 1.0,
  stop_loss: 2635.0,
  take_profit_1: 2670.0,
  take_profit_2: 2690.0,
  take_profit_3: 2710.0,
  time_in_force: "GTC" as const,
  idempotency_key: "idemp_test",
  creation_timestamp: Math.floor(Date.now() / 1000),
  lifecycle_state: "STAGED" as const,
  is_staged: true,
  is_terminal: false,
};

const snapshot = createHostSnapshotFromProject1(
  SAMPLE_CONNECTED_PORT,
  SAMPLE_REAL_PROJECT1_SIGNAL,
  "XAUUSD",
  "1h",
  undefined,
  undefined,
  [sampleIntent]
);

describe("OrderIntentViewer component", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders non-execution disclosure banner and staged intent cards", () => {
    render(
      <MemoryRouter>
        <I18nProvider>
          <OrderIntentViewer snapshot={snapshot} />
        </I18nProvider>
      </MemoryRouter>
    );

    expect(screen.getByText(/Non-Execution Disclosure/i)).not.toBeNull();
    expect(screen.getAllByText(/XAUUSD/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/BUY/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Cancel Intent/i).length).toBeGreaterThan(0);
  });

  it("filters order intents by symbol query", () => {
    render(
      <MemoryRouter>
        <I18nProvider>
          <OrderIntentViewer snapshot={snapshot} />
        </I18nProvider>
      </MemoryRouter>
    );

    const searchInput = screen.getByPlaceholderText(/Search intents by symbol/i);
    fireEvent.change(searchInput, { target: { value: "NON_EXISTENT_SYMBOL" } });

    expect(screen.getByText(/No Order Intents Found/i)).not.toBeNull();
  });

  it("handles cancel action on staged order intent", () => {
    const handleTransition = vi.fn();
    window.prompt = vi.fn().mockReturnValue("User requested cancellation");

    render(
      <MemoryRouter>
        <I18nProvider>
          <OrderIntentViewer snapshot={snapshot} onTransitionIntent={handleTransition} />
        </I18nProvider>
      </MemoryRouter>
    );

    const cancelButtons = screen.getAllByText("Cancel Intent");
    fireEvent.click(cancelButtons[0]);

    expect(handleTransition).toHaveBeenCalledWith(
      expect.stringContaining("ord_intent_"),
      "CANCELLED",
      "User requested cancellation"
    );
  });

  it("renders reconciliation status and handles request execution click", () => {
    const handleRequestExecution = vi.fn();
    const snapWithRec = {
      ...snapshot,
      orderIntents: [
        {
          ...snapshot.orderIntents![0],
          reconciliation: {
            reconciliation_id: "rec_100",
            order_intent_id: snapshot.orderIntents![0].order_intent_id,
            user_id: "user_test",
            status: "NOT_CONFIGURED" as const,
            internal_state: "STAGED",
            external_evidence_found: false,
            reason: "Fail-closed reconciliation: No external execution provider.",
            timestamp: 1700000000,
            last_check_timestamp: 1700000000,
            externally_executed: false,
          },
        },
      ],
    };

    render(
      <MemoryRouter>
        <I18nProvider>
          <OrderIntentViewer snapshot={snapWithRec} onRequestExecution={handleRequestExecution} />
        </I18nProvider>
      </MemoryRouter>
    );

    expect(screen.getByText(/Operational Execution Reconciliation/i)).not.toBeNull();
    const execBtn = screen.getByText(/Submit to Execution Boundary/i);
    fireEvent.click(execBtn);
    expect(handleRequestExecution).toHaveBeenCalledWith(expect.stringContaining("ord_intent_"));
  });
});

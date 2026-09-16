import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { SignalDeliveryCenter } from "./SignalDeliveryCenter";
import {
  createDisconnectedHostSnapshot,
  createHostSnapshotFromProject1,
  SAMPLE_CONNECTED_PORT,
  SAMPLE_REAL_PROJECT1_SIGNAL,
} from "../../architecture/hostView";
import { I18nProvider } from "../../i18n";

describe("SignalDeliveryCenter UI Component", () => {
  beforeEach(() => {
    cleanup();
    localStorage.clear();
  });

  it("renders outbound delivery dispatcher cards and audit log table", () => {
    const snapshot = createDisconnectedHostSnapshot();
    render(
      <I18nProvider>
        <SignalDeliveryCenter snapshot={snapshot} />
      </I18nProvider>
    );

    expect(screen.getByText("Outbound Signal Delivery Dispatcher")).toBeDefined();
    expect(screen.getByText("Telegram Bot Channel")).toBeDefined();
    expect(screen.getByText("In-App Signal Feed")).toBeDefined();
    expect(screen.getByText("Direct Outbound Webhook")).toBeDefined();
    expect(screen.getByText("Consumer Authorization Policy Evaluation")).toBeDefined();
  });

  it("triggers signal dispatch on button click when connected", async () => {
    const connectedSnapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL
    );

    render(
      <I18nProvider>
        <SignalDeliveryCenter snapshot={connectedSnapshot} />
      </I18nProvider>
    );

    const dispatchBtn = screen.getByRole("button", { name: "Dispatch Test Signal" });
    expect(dispatchBtn).toBeDefined();

    fireEvent.click(dispatchBtn);

    // Wait for async dispatch timeout
    await new Promise((resolve) => setTimeout(resolve, 500));

    expect(screen.getByText("DELIVERED")).toBeDefined();
    expect(screen.getByText("Signal delivered successfully")).toBeDefined();
  });

  it("renders correctly in Persian (fa) RTL language mode", () => {
    localStorage.setItem("ai_trading_lab_lang", "fa");
    const snapshot = createDisconnectedHostSnapshot();

    render(
      <I18nProvider>
        <SignalDeliveryCenter snapshot={snapshot} />
      </I18nProvider>
    );

    expect(screen.getByText("ارسال سیگنال خروجی و مدیریت کانال‌ها")).toBeDefined();
  });
});

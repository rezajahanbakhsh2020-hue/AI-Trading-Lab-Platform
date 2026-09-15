import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, expect, it, afterEach } from "vitest";
import { AIAssistant } from "./AIAssistant";
import { createDisconnectedHostSnapshot } from "../../architecture/hostView";
import { I18nProvider } from "../../i18n";

describe("AIAssistant UI Component", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders default unavailable state correctly", () => {
    const snapshot = createDisconnectedHostSnapshot("XAUUSD", "1h");
    const { container } = render(
      <I18nProvider>
        <AIAssistant snapshot={snapshot} />
      </I18nProvider>
    );

    expect(screen.getByTestId("ai-assistant-component")).not.toBeNull();
    expect(container.textContent).toContain("AI Assistant Gateway");
    expect(container.textContent).toContain("Security & Context Boundary");
    expect(container.textContent).toContain("No Provider (Default)");
  });

  it("handles processing request in default unavailable state", () => {
    const snapshot = createDisconnectedHostSnapshot("XAUUSD", "1h");
    const { container } = render(
      <I18nProvider>
        <AIAssistant snapshot={snapshot} />
      </I18nProvider>
    );

    const btn = screen.getByRole("button", { name: "Generate Explanation" });
    fireEvent.click(btn);

    expect(container.textContent).toContain("AI unavailable / provider not configured");
  });

  it("handles processing request with simulated available provider", () => {
    const snapshot = createDisconnectedHostSnapshot("XAUUSD", "1h");
    const { container } = render(
      <I18nProvider>
        <AIAssistant snapshot={snapshot} />
      </I18nProvider>
    );

    const select = screen.getByRole("combobox", { name: "Simulate Provider" });
    fireEvent.change(select, { target: { value: "available" } });

    const btn = screen.getByRole("button", { name: "Generate Explanation" });
    fireEvent.click(btn);

    expect(container.textContent).toContain("AI Explanation for EXPLAIN_SIGNAL (XAUUSD)");
    expect(container.textContent).toContain("HttpAIProviderAdapter");
  });

  it("handles processing request with simulated error condition", () => {
    const snapshot = createDisconnectedHostSnapshot("XAUUSD", "1h");
    const { container } = render(
      <I18nProvider>
        <AIAssistant snapshot={snapshot} />
      </I18nProvider>
    );

    const select = screen.getByRole("combobox", { name: "Simulate Provider" });
    fireEvent.change(select, { target: { value: "error" } });

    const btn = screen.getByRole("button", { name: "Generate Explanation" });
    fireEvent.click(btn);

    expect(container.textContent).toContain("AI provider request timed out.");
    expect(container.textContent).toContain("Request timed out");
  });
});

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, beforeEach } from "vitest";
import { AlertCenter } from "./AlertCenter";
import { createDisconnectedHostSnapshot } from "../../architecture/hostView";
import { I18nProvider } from "../../i18n";

describe("AlertCenter Component", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders alerts tab and rule manager tab buttons", () => {
    const snapshot = createDisconnectedHostSnapshot("XAUUSD");
    render(
      <I18nProvider>
        <AlertCenter snapshot={snapshot} />
      </I18nProvider>
    );

    const buttons = screen.getAllByRole("button");
    const ruleBtn = buttons.find((b) => b.textContent?.includes("Rule Manager"));
    expect(ruleBtn).toBeDefined();
  });

  it("allows switching to Rule Manager tab and shows rule form", () => {
    const snapshot = createDisconnectedHostSnapshot("XAUUSD");
    render(
      <I18nProvider>
        <AlertCenter snapshot={snapshot} />
      </I18nProvider>
    );

    const buttons = screen.getAllByRole("button");
    const ruleBtn = buttons.find((b) => b.textContent?.includes("Rule Manager"));
    expect(ruleBtn).toBeDefined();
    if (ruleBtn) {
      fireEvent.click(ruleBtn);
    }

    expect(screen.getByText(/Configured Alert Rules/i)).not.toBeNull();
    expect(screen.getByText(/Create Custom Alert Rule/i)).not.toBeNull();
  });
});

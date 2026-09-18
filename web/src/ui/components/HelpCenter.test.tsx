import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { I18nProvider } from "../../i18n/I18nContext";
import { EmptyState } from "./EmptyState";
import { HelpCenter } from "./HelpCenter";

describe("HelpCenter component", () => {
  it("renders help center title and header", () => {
    const { container } = render(
      <I18nProvider>
        <HelpCenter />
      </I18nProvider>
    );

    expect(container.textContent).toContain("Help, Guidance & Onboarding Center");
    expect(container.textContent).toContain("Comprehensive operational documentation");
  });
});

describe("EmptyState component", () => {
  it("renders title, message, and action link to help center", () => {
    render(
      <EmptyState
        title="No Data Available"
        message="There is no active data to display at this moment."
      />
    );

    expect(screen.getByText("No Data Available")).not.toBeNull();
    expect(
      screen.getByText("There is no active data to display at this moment.")
    ).not.toBeNull();
    expect(
      screen.getByRole("link", { name: /Need Help\? Visit Help Center/i })
    ).not.toBeNull();
  });
});

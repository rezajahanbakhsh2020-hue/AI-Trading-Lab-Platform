import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { I18nProvider } from "../../i18n/I18nContext";
import { OperationalErrorBanner } from "./OperationalErrorBanner";

describe("OperationalErrorBanner component", () => {
  it("renders error banner with structured guidance and correlation ID", () => {
    const { container } = render(
      <I18nProvider>
        <OperationalErrorBanner
          error={{
            whatHappenedKey: "Authentication failed",
            whyLikelyKey: "The supplied password does not match server records.",
            whatToCancelKey: "Verify your credentials and attempt to sign in again.",
            whatIfContinuesKey: "Contact system administration if password reset fails.",
            correlationId: "req_test_12345",
          }}
        />
      </I18nProvider>
    );

    expect(screen.getByRole("alert")).not.toBeNull();
    expect(screen.getByText("Authentication failed")).not.toBeNull();
    expect(
      screen.getByText("The supplied password does not match server records.")
    ).not.toBeNull();
    expect(
      screen.getByText("Verify your credentials and attempt to sign in again.")
    ).not.toBeNull();
    expect(container.textContent).toContain("req_test_12345");
  });
});

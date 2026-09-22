import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HealthCenter } from "./HealthCenter";
import {
  createDisconnectedHostSnapshot,
  createHostSnapshotFromProject1,
  SAMPLE_CONNECTED_PORT,
  SAMPLE_REAL_PROJECT1_SIGNAL,
} from "../../architecture/hostView";
import { I18nProvider } from "../../i18n";

describe("HealthCenter UI Component", () => {
  it("renders disconnected state correctly", () => {
    const snapshot = createDisconnectedHostSnapshot("XAUUSD", "1h");
    const { container } = render(
      <I18nProvider>
        <HealthCenter snapshot={snapshot} />
      </I18nProvider>
    );

    expect(screen.getByTestId("health-center-component")).not.toBeNull();
    expect(screen.getByText("OFFLINE")).not.toBeNull();
    expect(container.textContent).toContain("DisconnectedProject1Adapter");
  });

  it("renders connected state correctly", () => {
    const snapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL,
      "XAUUSD",
      "1h"
    );

    const { container } = render(
      <I18nProvider>
        <HealthCenter snapshot={snapshot} />
      </I18nProvider>
    );

    expect(container.querySelector('[data-testid="health-center-component"]')).not.toBeNull();
    expect(screen.getByText("ONLINE")).not.toBeNull();
    expect(container.textContent).toContain("Project1GatewayAdapter");
  });
});

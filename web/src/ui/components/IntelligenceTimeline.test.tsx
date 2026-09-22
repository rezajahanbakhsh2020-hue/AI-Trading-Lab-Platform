import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { IntelligenceTimeline } from "./IntelligenceTimeline";
import {
  createHostSnapshotFromProject1,
} from "../../architecture/hostView";
import {
  SAMPLE_CONNECTED_PORT,
  SAMPLE_REAL_PROJECT1_SIGNAL,
} from "../../architecture/testFixtures";
import { I18nProvider } from "../../i18n/I18nContext";

describe("IntelligenceTimeline Component", () => {
  it("renders timeline events and opens explainability modal on button click", () => {
    const snapshot = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL
    );

    render(
      <I18nProvider>
        <IntelligenceTimeline snapshot={snapshot} />
      </I18nProvider>
    );

    expect(screen.getByText(/Unified Intelligence Timeline/i)).not.toBeNull();
    expect(screen.getAllByText(/BUY Signal Emitted/i)[0]).not.toBeNull();

    const explainBtn = screen.getAllByText(/Explain Context/i)[0];
    fireEvent.click(explainBtn);

    expect(screen.getAllByText(/Explainability Layer/i)[0]).not.toBeNull();
    expect(screen.getAllByText(/Source & Freshness/i)[0]).not.toBeNull();
  });
});

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { BrowserRouter } from "react-router-dom";
import { CommandPalette } from "./CommandPalette";
import { I18nProvider } from "../../i18n";
import type { HostSnapshot } from "../../architecture/hostView";

const mockSnapshot: HostSnapshot = {
  generatedAt: null,
  platform: { name: "Platform", status: "ready", role: "Host application" },
  project1: { connected: true, port: "Port1", adapterName: "LabAdapter", status: "ready", message: "Connected" },
  market: {
    symbol: "XAUUSD",
    timeframe: "1h",
    status: "connected",
    provider: { id: "p1", name: "BiQuote", provider: "biquote", status: "connected", supportedTimeframes: ["1h"] },
    quote: { symbol: "XAUUSD", last: 2000, changePercent: 0.5, timestamp: 123456789 },
    candles: [],
    message: "Live",
    lastFetchedAt: null,
  },
  strategy: { name: "GoldStrategy", stability: 85, status: "active", message: "Active" },
  signal: { signalId: "sig_001", action: "BUY", timestamp: "123456789", confidence: 0.85, status: "ready", message: "Active signal" },
  risk: { entry: 2000, stopLoss: 1980, takeProfits: [2040, 2080], status: "available", message: "Calculated" },
  monitoring: { freshness: "Fresh", health: "healthy", status: "ready", message: "Ok" },
  providers: { marketData: "connected", quote: "connected", message: "Providers ready" },
  performance: { status: "unavailable", message: "No perf data" },
  security: { userId: "test_user", role: "user", isAdmin: false, permissions: ["read:signals"], status: "enforced", message: "Authorized" },
  authorization: {
    status: "AUTHORIZED",
    isAuthorized: true,
    reason: "autonomous execution authorized",
    checks: [],
    riskRewardRatio: 2.0,
    timestamp: 123456789,
  },
  activity: [],
};

describe("CommandPalette component", () => {
  it("renders when open and handles escape key to close", () => {
    const handleClose = vi.fn();
    render(
      <I18nProvider>
        <BrowserRouter>
          <CommandPalette
            isOpen={true}
            onClose={handleClose}
            snapshot={mockSnapshot}
          />
        </BrowserRouter>
      </I18nProvider>
    );

    const inputs = screen.getAllByPlaceholderText(/Search markets/i);
    expect(inputs.length).toBeGreaterThan(0);

    fireEvent.keyDown(inputs[0], { key: "Escape" });
    expect(handleClose).toHaveBeenCalled();
  });

  it("filters search results when typing", () => {
    render(
      <I18nProvider>
        <BrowserRouter>
          <CommandPalette
            isOpen={true}
            onClose={() => {}}
            snapshot={mockSnapshot}
          />
        </BrowserRouter>
      </I18nProvider>
    );

    const inputs = screen.getAllByPlaceholderText(/Search markets/i);
    fireEvent.change(inputs[0], { target: { value: "XAUUSD" } });

    const matches = screen.getAllByText("XAUUSD");
    expect(matches.length).toBeGreaterThan(0);
  });
});

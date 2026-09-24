import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { App } from "./App";
import { I18nProvider } from "../i18n/I18nContext";

// Mock lightweight-charts to avoid Canvas context errors in jsdom environment
vi.mock("lightweight-charts", () => {
  const mockSeries = {
    setData: vi.fn(),
    createPriceLine: vi.fn(),
    applyOptions: vi.fn(),
  };

  const mockChart = {
    addSeries: vi.fn().mockReturnValue(mockSeries),
    removeSeries: vi.fn(),
    priceScale: vi.fn().mockReturnValue({
      applyOptions: vi.fn(),
    }),
    subscribeCrosshairMove: vi.fn(),
    timeScale: vi.fn().mockReturnValue({
      fitContent: vi.fn(),
    }),
    applyOptions: vi.fn(),
    remove: vi.fn(),
  };

  return {
    createChart: vi.fn().mockReturnValue(mockChart),
    CandlestickSeries: { type: "Candlestick" },
    LineSeries: { type: "Line" },
    AreaSeries: { type: "Area" },
    HistogramSeries: { type: "Histogram" },
    createSeriesMarkers: vi.fn(),
    ColorType: { Solid: "solid" },
    LineStyle: { Dashed: 2 },
    CrosshairMode: { Normal: 0 },
  };
});

// Mock ResizeObserver
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Mock matchMedia
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

describe("Layout Invariants and Responsive Architecture", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("dir");
    document.documentElement.removeAttribute("lang");
  });

  it("renders App Shell with root sizing constraints and workspace container bounds", () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/"]}>
        <I18nProvider>
          <App />
        </I18nProvider>
      </MemoryRouter>
    );

    const appShell = container.querySelector(".app-shell");
    expect(appShell).not.toBeNull();
    expect(appShell?.className).toContain("app-shell");

    const workspace = container.querySelector(".workspace");
    expect(workspace).not.toBeNull();
  });

  it("propagates RTL directionality to document element and app shell for RTL locales", () => {
    localStorage.setItem("ai_trading_lab_lang", "fa");

    render(
      <MemoryRouter initialEntries={["/"]}>
        <I18nProvider>
          <App />
        </I18nProvider>
      </MemoryRouter>
    );

    expect(document.documentElement.getAttribute("dir")).toBe("rtl");
    expect(document.documentElement.getAttribute("lang")).toBe("fa");
  });

  it("renders navigation surfaces (TopBar, DesktopSidebar, MobileBottomNav) without crashing", () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/signals"]}>
        <I18nProvider>
          <App />
        </I18nProvider>
      </MemoryRouter>
    );

    expect(container.querySelector(".topbar")).not.toBeNull();
    expect(container.querySelector(".sidebar")).not.toBeNull();
    expect(container.querySelector(".mobile-bottom-dock")).not.toBeNull();
  });

  it("renders route view containers inside main workspace container obeying parent constraints", () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/screener"]}>
        <I18nProvider>
          <App />
        </I18nProvider>
      </MemoryRouter>
    );

    const workspace = container.querySelector("main.workspace");
    expect(workspace).not.toBeNull();
    expect(workspace?.children.length).toBeGreaterThan(0);
  });

  it("enforces canonical BoundedPageContainer boundary across all registered routes", () => {
    const testRoutes = [
      "/",
      "/dashboard",
      "/timeline",
      "/screener",
      "/markets",
      "/watchlist",
      "/signals",
      "/strategies",
      "/backtest",
      "/performance",
      "/risk",
      "/audit",
      "/intents",
      "/users",
      "/health",
      "/monitoring",
      "/providers",
      "/academy",
      "/ai",
      "/alerts",
      "/notifications",
      "/help",
      "/settings",
    ];

    for (const route of testRoutes) {
      const { container, unmount } = render(
        <MemoryRouter initialEntries={[route]}>
          <I18nProvider>
            <App />
          </I18nProvider>
        </MemoryRouter>
      );

      const boundedContainer = container.querySelector(".bounded-page-container");
      expect(boundedContainer).not.toBeNull();
      expect(boundedContainer?.getAttribute("data-testid")).toBe("bounded-page-container");
      expect(boundedContainer?.getAttribute("data-mobile-geometry-contract")).toBe("true");

      // Verify container style invariants
      const style = (boundedContainer as HTMLElement).style;
      expect(style.width).toBe("100%");
      expect(style.maxWidth).toBe("100%");
      expect(style.minWidth).toBe("0px");

      // Verify table elements are wrapped inside .table-responsive
      const tables = container.querySelectorAll("table");
      tables.forEach((tbl) => {
        const responsiveParent = tbl.closest(".table-responsive");
        expect(responsiveParent).not.toBeNull();
      });

      unmount();
    }
  });

  it("verifies BoundedTableWrapper and BoundedModal primitives adhere to mobile geometry bounds", async () => {
    const { BoundedTableWrapper, BoundedModal } = await import("./components/BoundedPageContainer");

    const { container: tableContainer } = render(
      <BoundedTableWrapper>
        <table>
          <tbody>
            <tr>
              <td>Test Table Data</td>
            </tr>
          </tbody>
        </table>
      </BoundedTableWrapper>
    );

    const tblWrapper = tableContainer.querySelector(".table-responsive");
    expect(tblWrapper).not.toBeNull();
    const tblWrapperStyle = (tblWrapper as HTMLElement).style;
    expect(tblWrapperStyle.width).toBe("100%");
    expect(tblWrapperStyle.maxWidth).toBe("100%");
    expect(tblWrapperStyle.overflowX).toBe("auto");

    const { container: modalContainer } = render(
      <BoundedModal maxWidthPx={480}>
        <div>Modal Content</div>
      </BoundedModal>
    );

    const modalEl = modalContainer.querySelector(".modal-card");
    expect(modalEl).not.toBeNull();
    const modalStyle = (modalEl as HTMLElement).style;
    expect(modalStyle.width).toBe("100%");
    expect(modalStyle.maxWidth).toBe("min(100%, 480px)");
  });
});

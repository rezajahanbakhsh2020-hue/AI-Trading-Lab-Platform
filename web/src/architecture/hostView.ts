export const PLATFORM_NAME = "AI Trading Lab Platform";
export const PLATFORM_ROLE = "Host application for AI-Trading-Lab";
export const PRIMARY_MARKET = "XAUUSD";

export const NAV_ITEMS = [
  { id: "dashboard", path: "/", label: "Dashboard" },
  { id: "market", path: "/market", label: "Market" },
  { id: "strategy", path: "/strategy", label: "Strategy" },
  { id: "backtest", path: "/backtest", label: "Backtest" },
  { id: "signals", path: "/signals", label: "Signals" },
  { id: "performance", path: "/performance", label: "Performance" },
  { id: "risk", path: "/risk", label: "Risk" },
  { id: "monitoring", path: "/monitoring", label: "Monitoring" },
  { id: "providers", path: "/providers", label: "Providers" },
  { id: "logs", path: "/logs", label: "Logs" },
  { id: "settings", path: "/settings", label: "Settings" },
] as const;

export const INTEGRATION_FLOW = [
  {
    id: "project1",
    label: "AI-Trading-Lab",
    role: "Strategy and decision engine",
  },
  {
    id: "port",
    label: "Integration boundary",
    role: "Project1IntegrationPort and platform adapters",
  },
  {
    id: "host",
    label: "AI-Trading-Lab-Platform",
    role: "Host, presentation, and delivery",
  },
  {
    id: "ui",
    label: "Application UI",
    role: "Human-facing terminal",
  },
] as const;

export const UNAVAILABLE = "Unavailable";
export const DISCONNECTED_MESSAGE = "No Project 1 data connected yet.";

export function createDisconnectedHostSnapshot() {
  return {
    generatedAt: null as string | null,
    platform: {
      name: PLATFORM_NAME,
      role: PLATFORM_ROLE,
      status: "ready" as const,
    },
    project1: {
      connected: false,
      status: "disconnected" as const,
      port: "Project1IntegrationPort",
      message: DISCONNECTED_MESSAGE,
    },
    market: {
      symbol: PRIMARY_MARKET,
      timeframe: null as string | null,
      quote: null as number | null,
      change: null as number | null,
      volume: null as number | null,
      candles: [] as readonly never[],
      status: "unavailable" as const,
      message: "Market data is unavailable until a provider is connected.",
    },
    strategy: {
      name: null as string | null,
      stability: null as number | null,
      status: "unavailable" as const,
      message: "Strategy information is provided by Project 1.",
    },
    signal: {
      action: null as string | null,
      timestamp: null as string | null,
      status: "unavailable" as const,
      message: DISCONNECTED_MESSAGE,
    },
    performance: {
      status: "unavailable" as const,
      message: "Performance metrics are unavailable until Project 1 results are connected.",
    },
    risk: {
      entry: null as number | null,
      stopLoss: null as number | null,
      takeProfits: [] as readonly number[],
      status: "unavailable" as const,
      message: "Risk levels are unavailable until a real trade setup is provided.",
    },
    monitoring: {
      freshness: null as string | null,
      health: null as string | null,
      status: "unavailable" as const,
      message: "Monitoring has no live observations yet.",
    },
    providers: {
      marketData: "unconnected" as const,
      quote: "unconnected" as const,
      message: "Provider slots are ready. No live provider session is attached.",
    },
    activity: [] as readonly never[],
  };
}

export type HostSnapshot = ReturnType<typeof createDisconnectedHostSnapshot>;

export const PAGE_COPY: Record<
  string,
  { title: string; kicker: string; summary: string }
> = {
  dashboard: {
    title: "Dashboard",
    kicker: "Host overview",
    summary: "Operational home for presenting Project 1 inside Project 2.",
  },
  market: {
    title: "Market",
    kicker: "Primary market XAU/USD",
    summary: "Chart, quote, and volume surfaces consume provider data through existing platform ports.",
  },
  strategy: {
    title: "Strategy",
    kicker: "Project 1 owned",
    summary: "This host displays strategy identity and state. It does not generate strategies.",
  },
  backtest: {
    title: "Backtest",
    kicker: "Assessment surface",
    summary: "Backtest results will appear here from Project 1 through the existing assessment boundary.",
  },
  signals: {
    title: "Signals",
    kicker: "Presentation and delivery",
    summary: "Signals are presented only when Project 1 emits them through the integration port.",
  },
  performance: {
    title: "Performance",
    kicker: "Observed results",
    summary: "Performance figures are shown only from connected Project 1 assessments.",
  },
  risk: {
    title: "Risk",
    kicker: "Trade setup levels",
    summary: "Entry, stop loss, and take-profit levels stay empty until a real setup is supplied.",
  },
  monitoring: {
    title: "Monitoring",
    kicker: "Health and freshness",
    summary: "Live monitoring uses existing provider health and freshness contracts.",
  },
  providers: {
    title: "Providers",
    kicker: "Data boundary",
    summary: "Market-data and quote providers attach through the existing registry and readiness gate.",
  },
  logs: {
    title: "Logs",
    kicker: "Host activity",
    summary: "Operational events from the host application will appear here when recorded.",
  },
  settings: {
    title: "Settings",
    kicker: "Host configuration",
    summary: "This platform does not store exchange API keys or execute real-money orders.",
  },
};

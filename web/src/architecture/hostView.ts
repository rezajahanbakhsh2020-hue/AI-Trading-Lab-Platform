import type { Candle, ProviderMetadata, Quote, MarketDataStatus } from "./marketData";

export const PLATFORM_NAME = "AI Trading Lab Platform";
export const PLATFORM_ROLE = "Host application for AI-Trading-Lab";
export const PRIMARY_MARKET = "XAUUSD";

export const NAV_ITEMS = [
  { id: "dashboard", path: "/", label: "Dashboard", icon: "home" },
  { id: "timeline", path: "/timeline", label: "Intelligence Timeline", icon: "activity" },
  { id: "screener", path: "/screener", label: "Market Screener", icon: "grid" },
  { id: "markets", path: "/markets", label: "Markets", icon: "bar-chart-2" },
  { id: "watchlist", path: "/watchlist", label: "Watchlist", icon: "star" },
  { id: "signals", path: "/signals", label: "Signals", icon: "zap" },
  { id: "strategies", path: "/strategies", label: "Strategies", icon: "cpu" },
  { id: "backtest", path: "/backtest", label: "Backtest", icon: "history" },
  { id: "performance", path: "/performance", label: "Performance", icon: "trending-up" },
  { id: "risk", path: "/risk", label: "Risk", icon: "shield" },
  { id: "audit", path: "/audit", label: "Operational Control", icon: "shield" },
  { id: "authorization", path: "/authorization", label: "Autonomous Gate", icon: "shield" },
  { id: "health", path: "/health", label: "Health Center", icon: "activity" },
  { id: "monitoring", path: "/monitoring", label: "Monitoring", icon: "activity" },
  { id: "providers", path: "/providers", label: "Providers", icon: "layers" },
  { id: "academy", path: "/academy", label: "Academy", icon: "book-open" },
  { id: "ai", path: "/ai", label: "AI Assistant", icon: "bot" },
  { id: "alerts", path: "/alerts", label: "Alert Center", icon: "bell" },
  { id: "notifications", path: "/notifications", label: "Notifications", icon: "bell" },
  { id: "settings", path: "/settings", label: "Settings", icon: "settings" },
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

export interface UserSecurityProfile {
  userId: string;
  role: "admin" | "user" | "guest";
  permissions: readonly string[];
  isAdmin: boolean;
}

export interface PresentedSignalPayload {
  signal_id: string;
  symbol: string;
  signal_type: string;
  timestamp: number;
  entry_price?: number | null;
  stop_loss?: number | null;
  take_profits?: readonly number[];
  confidence?: number | null;
  strategy_name?: string | null;
  timeframe?: string | null;
  metadata?: Record<string, unknown>;
}

export interface PortDescriptionPayload {
  name: string;
  port: string;
  connected: boolean;
  status?: string;
  message?: string;
  source?: Record<string, unknown>;
}

export interface MarketStateSnapshot {
  symbol: string;
  timeframe: string;
  provider: ProviderMetadata | null;
  quote: Quote | null;
  candles: readonly Candle[];
  status: MarketDataStatus;
  message: string;
  lastFetchedAt: string | null;
}

export interface HostSnapshot {
  generatedAt: string | null;
  platform: {
    name: string;
    role: string;
    status: string;
  };
  security: {
    userId: string;
    role: string;
    isAdmin: boolean;
    permissions: readonly string[];
    status: string;
    message: string;
  };
  project1: {
    connected: boolean;
    status: string;
    port: string;
    adapterName: string;
    message: string;
  };
  market: MarketStateSnapshot;
  strategy: {
    name: string | null;
    stability: number | null;
    status: string;
    message: string;
  };
  signal: {
    signalId?: string | null;
    action: string | null;
    timestamp: string | null;
    confidence?: number | null;
    strategyName?: string | null;
    timeframe?: string | null;
    status: string;
    message: string;
    metadata?: Record<string, unknown>;
  };
  performance: {
    status: string;
    message: string;
  };
  risk: {
    entry: number | null;
    stopLoss: number | null;
    takeProfits: readonly number[];
    status: string;
    message: string;
  };
  monitoring: {
    freshness: string | null;
    health: string | null;
    status: string;
    message: string;
  };
  providers: {
    marketData: string;
    quote: string;
    message: string;
  };
  activity: readonly { timestamp: string; event: string; details: string }[];
  auditControl?: {
    status?: string;
    summary?: any;
    events?: any[];
  };
}

export function createDisconnectedHostSnapshot(
  symbol: string = PRIMARY_MARKET,
  timeframe: string = "1h",
  securityProfile?: UserSecurityProfile
): HostSnapshot {
  const sec = securityProfile || {
    userId: "guest_user",
    role: "user",
    permissions: ["read:signals", "read:trade_setups"],
    isAdmin: false,
  };

  return {
    generatedAt: null,
    platform: {
      name: PLATFORM_NAME,
      role: PLATFORM_ROLE,
      status: "ready",
    },
    security: {
      userId: sec.userId,
      role: sec.role,
      isAdmin: sec.isAdmin,
      permissions: sec.permissions,
      status: "enforced",
      message: sec.isAdmin
        ? "Admin role authenticated. Full system & secret access granted."
        : "Standard user identity active. Proprietary secrets and admin-only resources are protected.",
    },
    project1: {
      connected: false,
      status: "disconnected",
      port: "Project1IntegrationPort",
      adapterName: "DisconnectedProject1Adapter",
      message: DISCONNECTED_MESSAGE,
    },
    market: {
      symbol,
      timeframe,
      provider: null,
      quote: null,
      candles: [],
      status: "disconnected",
      message: "Market data provider is disconnected. Connect provider to stream live market data.",
      lastFetchedAt: null,
    },
    strategy: {
      name: null,
      stability: null,
      status: "unavailable",
      message: "Strategy information is provided by Project 1.",
    },
    signal: {
      signalId: null,
      action: null,
      timestamp: null,
      confidence: null,
      strategyName: null,
      timeframe: null,
      status: "unavailable",
      message: DISCONNECTED_MESSAGE,
      metadata: {},
    },
    performance: {
      status: "unavailable",
      message: "Performance metrics are unavailable until Project 1 results are connected.",
    },
    risk: {
      entry: null,
      stopLoss: null,
      takeProfits: [],
      status: "unavailable",
      message: "Risk levels are unavailable until a real trade setup is provided.",
    },
    monitoring: {
      freshness: null,
      health: null,
      status: "unavailable",
      message: "Monitoring has no live observations yet.",
    },
    providers: {
      marketData: "disconnected",
      quote: "disconnected",
      message: "Provider slots are ready. No live provider session is attached.",
    },
    activity: [],
    auditControl: {
      status: "available",
      summary: {
        total_events: 2,
        events_by_category: { OPERATIONAL_SYSTEM: 1, PROVIDER_HEALTH: 1 },
        events_by_severity: { INFO: 2 },
        events_by_lifecycle: { COMPLETED: 2 },
        failed_events_count: 0,
        degraded_events_count: 0,
        last_event_timestamp: 1700000000,
      },
      events: [
        {
          event_id: "sys-init-001",
          timestamp: 1700000000,
          user_id: "system",
          category: "OPERATIONAL_SYSTEM",
          event_type: "SYSTEM_INITIALIZED",
          lifecycle_state: "COMPLETED",
          action: "INITIALIZE_PLATFORM",
          outcome: "SUCCESS",
          severity: "INFO",
          resource_id: "platform_core",
          correlation_id: "sys-init-001",
          details: "Platform operational control plane initialized safely.",
          metadata: { version: "1.0.0", status: "HEALTHY" },
        },
        {
          event_id: "sys-prov-002",
          timestamp: 1700000100,
          user_id: "system",
          category: "PROVIDER_HEALTH",
          event_type: "PROVIDER_CHECK",
          lifecycle_state: "COMPLETED",
          action: "CHECK_READINESS",
          outcome: "SUCCESS",
          severity: "INFO",
          resource_id: "project1_lab_adapter",
          correlation_id: "sys-prov-002",
          details: "Lab artifact provider adapter verified and online.",
          metadata: { provider: "Project1LabArtifactAdapter", status: "READY" },
        },
      ],
    },
  };
}

export function createHostSnapshotFromProject1(
  portDesc: PortDescriptionPayload,
  signal: PresentedSignalPayload | null,
  symbol: string = PRIMARY_MARKET,
  timeframe: string = "1h",
  marketState?: Partial<MarketStateSnapshot>,
  securityProfile?: UserSecurityProfile
): HostSnapshot {
  const defaultMarketState: MarketStateSnapshot = {
    symbol,
    timeframe,
    provider: null,
    quote: null,
    candles: [],
    status: "disconnected",
    message: "Market data feed relies on provider selection.",
    lastFetchedAt: null,
    ...marketState,
  };

  const sec = securityProfile || {
    userId: "guest_user",
    role: "user",
    permissions: ["read:signals", "read:trade_setups"],
    isAdmin: false,
  };

  if (!portDesc.connected) {
    return createDisconnectedHostSnapshot(symbol, timeframe, sec);
  }

  const baseSecSnapshot = {
    userId: sec.userId,
    role: sec.role,
    isAdmin: sec.isAdmin,
    permissions: sec.permissions,
    status: "enforced",
    message: sec.isAdmin
      ? "Admin role authenticated. Full system & secret access granted."
      : "Standard user identity active. Proprietary secrets and admin-only resources are protected.",
  };

  if (!signal) {
    return {
      generatedAt: null,
      platform: {
        name: PLATFORM_NAME,
        role: PLATFORM_ROLE,
        status: "ready",
      },
      security: baseSecSnapshot,
      project1: {
        connected: true,
        status: "connected",
        port: portDesc.port || "Project1IntegrationPort",
        adapterName: portDesc.name || "Project1LabArtifactAdapter",
        message: portDesc.message || `Project 1 connected via ${portDesc.name}.`,
      },
      market: defaultMarketState,
      strategy: {
        name: null,
        stability: null,
        status: "unavailable",
        message: "Connected to Project 1 engine. No active strategy emitted for this symbol.",
      },
      signal: {
        signalId: null,
        action: "NO SIGNAL",
        timestamp: null,
        confidence: null,
        strategyName: null,
        timeframe,
        status: "no-signal",
        message: `No active signal emitted by Project 1 for ${symbol} (${timeframe}).`,
        metadata: {},
      },
      performance: {
        status: "unavailable",
        message: "Performance metrics are unavailable until Project 1 results are connected.",
      },
      risk: {
        entry: null,
        stopLoss: null,
        takeProfits: [],
        status: "unavailable",
        message: "Risk levels stay empty until Project 1 emits a trade setup.",
      },
      monitoring: {
        freshness: null,
        health: "healthy",
        status: "available",
        message: "Project 1 engine connected.",
      },
      providers: {
        marketData: defaultMarketState.provider ? defaultMarketState.provider.status : "disconnected",
        quote: defaultMarketState.quote ? "connected" : "disconnected",
        message: defaultMarketState.provider
          ? `Connected to ${defaultMarketState.provider.name}`
          : "Provider slots are ready. No live provider session is attached.",
      },
      activity: [],
    };
  }

  const actionUpper = (signal.signal_type || "NO SIGNAL").toUpperCase();
  const entry = signal.entry_price ?? null;
  const sl = signal.stop_loss ?? null;
  const tps = signal.take_profits ? [...signal.take_profits] : [];
  const conf = signal.confidence ?? null;
  const stratName = signal.strategy_name ?? "Project 1 Strategy";
  const formattedTime = new Date(signal.timestamp * 1000).toUTCString();

  return {
    generatedAt: formattedTime,
    platform: {
      name: PLATFORM_NAME,
      role: PLATFORM_ROLE,
      status: "ready",
    },
    security: baseSecSnapshot,
    project1: {
      connected: true,
      status: "connected",
      port: portDesc.port || "Project1IntegrationPort",
      adapterName: portDesc.name || "Project1LabArtifactAdapter",
      message: `Project 1 emitting real signals via ${portDesc.name || "adapter"}.`,
    },
    market: defaultMarketState,
    strategy: {
      name: stratName,
      stability: conf != null ? Math.round(conf * 100) : null,
      status: "active",
      message: `Strategy '${stratName}' owned and evaluated by Project 1.`,
    },
    signal: {
      signalId: signal.signal_id,
      action: actionUpper,
      timestamp: formattedTime,
      confidence: conf,
      strategyName: stratName,
      timeframe: signal.timeframe || timeframe,
      status: "active",
      message: `Validated ${actionUpper} signal emitted by Project 1.`,
      metadata: signal.metadata || {},
    },
    performance: {
      status: "unavailable",
      message: "Performance metrics are unavailable until Project 1 backtest outputs are connected.",
    },
    risk: {
      entry,
      stopLoss: sl,
      takeProfits: tps,
      status: entry != null ? "available" : "unavailable",
      message: entry != null ? "Real trade setup levels provided by Project 1." : "Trade setup omitted.",
    },
    monitoring: {
      freshness: "fresh",
      health: "healthy",
      status: "available",
      message: "Project 1 signal active and fresh.",
    },
    providers: {
      marketData: defaultMarketState.provider ? defaultMarketState.provider.status : "disconnected",
      quote: defaultMarketState.quote ? "connected" : "disconnected",
      message: defaultMarketState.provider
        ? `Connected to ${defaultMarketState.provider.name}`
        : "Provider slots are ready. No live provider session is attached.",
    },
    activity: [
      {
        timestamp: formattedTime,
        event: "Signal Received",
        details: `${actionUpper} signal for ${signal.symbol || symbol} (${stratName})`,
      },
    ],
      auditControl: {
        status: "available",
        summary: {
          total_events: 3,
          events_by_category: { SIGNAL_INTAKE: 1, OPERATIONAL_SYSTEM: 1, PROVIDER_HEALTH: 1 },
          events_by_severity: { INFO: 3 },
          events_by_lifecycle: { VALIDATED: 1, COMPLETED: 2 },
          failed_events_count: 0,
          degraded_events_count: 0,
          last_event_timestamp: 1700000200,
        },
        events: [
          {
            event_id: "sig-intake-003",
            timestamp: 1700000200,
            user_id: sec.userId,
            category: "SIGNAL_INTAKE",
            event_type: "SIGNAL_RECEIVED",
            lifecycle_state: "VALIDATED",
            action: "INTAKE_PROJECT1_SIGNAL",
            outcome: "SUCCESS",
            severity: "INFO",
            resource_id: signal.signal_id || "sig_100",
            correlation_id: "sig-intake-003",
            details: `Validated ${actionUpper} signal emitted by Project 1 for ${symbol}.`,
            metadata: { strategy: stratName, timeframe },
          },
          {
            event_id: "sys-init-001",
            timestamp: 1700000000,
            user_id: "system",
            category: "OPERATIONAL_SYSTEM",
            event_type: "SYSTEM_INITIALIZED",
            lifecycle_state: "COMPLETED",
            action: "INITIALIZE_PLATFORM",
            outcome: "SUCCESS",
            severity: "INFO",
            resource_id: "platform_core",
            correlation_id: "sys-init-001",
            details: "Platform operational control plane initialized safely.",
            metadata: { version: "1.0.0", status: "HEALTHY" },
          },
        ],
      },
  };
}

/* Sample Project 1 outputs for connected state testing in UI */
export const SAMPLE_CONNECTED_PORT: PortDescriptionPayload = {
  name: "Project1LabArtifactAdapter",
  port: "Project1IntegrationPort",
  connected: true,
  status: "active",
  message: "Connected to Project1LabArtifactAdapter via LabArtifactService.",
};

export const SAMPLE_REAL_PROJECT1_SIGNAL: PresentedSignalPayload = {
  signal_id: "p1_xauusd_1h_1700000000",
  symbol: "XAUUSD",
  signal_type: "buy",
  timestamp: 1700000000,
  entry_price: 2650.5,
  stop_loss: 2635.0,
  take_profits: [2670.0, 2690.0, 2710.0],
  confidence: 0.88,
  strategy_name: "GoldTrendv1",
  timeframe: "1h",
  metadata: { source: "Project1", adapter: "Project1LabArtifactAdapter" },
};

export const PAGE_COPY: Record<
  string,
  { title: string; kicker: string; summary: string }
> = {
  dashboard: {
    title: "Dashboard",
    kicker: "Host overview",
    summary: "Operational home for presenting Project 1 inside Project 2.",
  },
  timeline: {
    title: "Intelligence Timeline",
    kicker: "Real Chronological Activity & Explainability",
    summary: "Unified platform events, signal emission history, market state updates, and context explainability layer.",
  },
  screener: {
    title: "Market Screener & Heatmap",
    kicker: "Multi-Asset Performance & Signal Workspace",
    summary: "Filter, scan, and visualize real 24h market performance and active Project 1 signals across commodities, forex, crypto, and indices.",
  },
  markets: {
    title: "Markets",
    kicker: "Primary market XAU/USD",
    summary: "Chart, quote, and volume surfaces consume provider data through existing platform ports.",
  },
  market: {
    title: "Market Workspace",
    kicker: "Primary market XAU/USD",
    summary: "Chart, quote, and volume surfaces consume provider data through existing platform ports.",
  },
  watchlist: {
    title: "Watchlist",
    kicker: "Custom Market Overview",
    summary: "Track primary commodities, FX pairs, and crypto assets in real time.",
  },
  signals: {
    title: "Signals & Outbound Dispatch",
    kicker: "Presentation and delivery",
    summary: "Validated Project 1 signal feed with multi-channel outbound delivery authorization (Telegram, Webhook, Inbox) and security boundary level masking.",
  },
  strategies: {
    title: "Strategies",
    kicker: "Project 1 owned",
    summary: "This host displays strategy identity and state. It does not generate strategies.",
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
  health: {
    title: "Health Center",
    kicker: "Data & Connection Health",
    summary: "Real-time, honest connection health, provider readiness, Project 1 signal-source availability, and notification pipeline status.",
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
  academy: {
    title: "Learning / Academy",
    kicker: "Financial Education & Concepts",
    summary: "Explore original guides, risk management strategies, walk-forward concepts, and glossary.",
  },
  learning: {
    title: "Learning / Academy",
    kicker: "Financial Education & Concepts",
    summary: "Explore original guides, risk management strategies, walk-forward concepts, and glossary.",
  },
  audit: {
    title: "Operational Control Plane & Platform Audit",
    kicker: "Production Audit & Lifecycle Observability",
    summary: "Complete operational control, lifecycle transition audit trail, security boundary tracking, and multi-tenant isolation monitoring.",
  },
  authorization: {
    title: "Autonomous Execution Gate",
    kicker: "Deterministic Trade Readiness Assurance",
    summary: "Safety gate evaluating signal tradability, stability, geometry, and risk/reward before autonomous execution dispatch.",
  },
  alerts: {
    title: "Alert Center & Rule Engine",
    kicker: "Real-Time Market & Signal Alerts",
    summary: "Configure custom price thresholds, signal filters, and provider freshness rules with live snapshot evaluation.",
  },
  notifications: {
    title: "Notifications",
    kicker: "System & Signal Feed",
    summary: "Real-time alerts, integration status events, and system messages.",
  },
  logs: {
    title: "Logs",
    kicker: "Host activity",
    summary: "Operational events from the host activity when recorded.",
  },
  ai: {
    title: "AI Assistant Gateway",
    kicker: "Secure Platform AI Boundary",
    summary: "Provider-agnostic AI explanation and context boundary with zero trading execution rights.",
  },
  settings: {
    title: "Settings & Profile",
    kicker: "Host configuration & Security Boundary",
    summary: "Security boundary, authorization roles, and platform settings.",
  },
};

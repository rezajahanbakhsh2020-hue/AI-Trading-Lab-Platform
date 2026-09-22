import type { HostSnapshot } from "./hostView";
import type { NotificationItem } from "./notification";

export type TimelineCategory =
  | "market"
  | "signal"
  | "notification"
  | "health"
  | "workspace"
  | "market_intelligence"
  | "system";

export type TimelineSeverity = "info" | "success" | "warning" | "error";

export interface TimelineItem {
  itemId: string;
  timestamp: number;
  formattedTime: string;
  category: TimelineCategory;
  severity: TimelineSeverity;
  title: string;
  summary: string;
  source: string;
  route: string;
  explainable: boolean;
  payload: Record<string, unknown>;
}

export interface ExplainabilityPayload {
  itemId: string;
  itemType: string;
  receivedAt: string;
  source: string;
  freshnessStatus: string;
  permittedMetadata: Record<string, unknown>;
  permittedMarketContext: Record<string, unknown>;
  permittedRiskContext: Record<string, unknown>;
  explainabilityNotes: string[];
}

export function extractTimelineFromHostSnapshot(
  snapshot: HostSnapshot,
  notifications: readonly NotificationItem[] = []
): TimelineItem[] {
  const items: TimelineItem[] = [];

  // 1. Signal Timeline Events (only active live signals, never NO SIGNAL or stale/historical)
  if (
    snapshot.signal &&
    snapshot.signal.status === "active" &&
    snapshot.signal.signalId &&
    snapshot.signal.action &&
    snapshot.signal.action !== "NO SIGNAL" &&
    snapshot.signal.action !== "STALE SIGNAL"
  ) {
    const sig = snapshot.signal;
    const action = sig.action;
    const tsStr = sig.timestamp || snapshot.generatedAt || new Date().toISOString();
    const tsVal = Date.parse(tsStr) || Date.now();

    items.push({
      itemId: `sig-${sig.signalId}`,
      timestamp: tsVal,
      formattedTime: new Date(tsVal).toUTCString(),
      category: "signal",
      severity: action === "BUY" || action === "SELL" ? "success" : "info",
      title: `${action} Signal Emitted (${snapshot.market?.symbol || "XAUUSD"})`,
      summary: sig.message || `Signal action ${action} emitted by ${sig.strategyName || "Project 1"}.`,
      source: snapshot.project1?.adapterName || "Project1GatewayAdapter",
      route: "/signals",
      explainable: true,
      payload: {
        signalId: sig.signalId,
        action,
        symbol: snapshot.market?.symbol,
        timeframe: sig.timeframe,
        confidence: sig.confidence,
        strategyName: sig.strategyName,
        status: sig.status,
        metadata: sig.metadata || {},
      },
    });
  }

  // 2. Market Events & Quote Context
  if (snapshot.market) {
    const mkt = snapshot.market;
    const tsStr = mkt.lastFetchedAt || snapshot.generatedAt || new Date().toISOString();
    const tsVal = Date.parse(tsStr) || Date.now();

    items.push({
      itemId: `mkt-${mkt.symbol.toLowerCase()}`,
      timestamp: tsVal,
      formattedTime: new Date(tsVal).toUTCString(),
      category: "market",
      severity: mkt.status === "connected" ? "info" : "warning",
      title: `Market Feed: ${mkt.symbol}`,
      summary: mkt.message || `Market data status: ${mkt.status}`,
      source: mkt.provider?.name || "MarketDataService",
      route: "/markets",
      explainable: true,
      payload: {
        symbol: mkt.symbol,
        timeframe: mkt.timeframe,
        status: mkt.status,
        quote: mkt.quote,
        provider: mkt.provider,
      },
    });
  }

  // 3. User Notifications Feed
  for (const notif of notifications) {
    let cat: TimelineCategory = "notification";
    if (notif.category === "signal") cat = "signal";
    else if (notif.category === "market_health") cat = "health";
    else if (notif.category === "workspace") cat = "workspace";

    let sev: TimelineSeverity = "info";
    if (notif.severity === "success") sev = "success";
    else if (notif.severity === "warning") sev = "warning";
    else if (notif.severity === "error") sev = "error";

    items.push({
      itemId: `notif-${notif.id}`,
      timestamp: notif.rawTimestamp,
      formattedTime: notif.timestamp,
      category: cat,
      severity: sev,
      title: notif.title,
      summary: notif.message,
      source: "NotificationCenter",
      route: "/notifications",
      explainable: false,
      payload: notif.metadata || {},
    });
  }

  // 4. Health & System Monitoring Events
  if (snapshot.monitoring) {
    const mon = snapshot.monitoring;
    const tsVal = Date.now();

    items.push({
      itemId: "health-system-mon",
      timestamp: tsVal,
      formattedTime: new Date(tsVal).toUTCString(),
      category: "health",
      severity: mon.health === "healthy" ? "success" : "warning",
      title: "Data & Health Status Check",
      summary: mon.message || "Freshness and provider readiness evaluated.",
      source: "ProviderMonitoringService",
      route: "/health",
      explainable: true,
      payload: {
        freshness: mon.freshness,
        health: mon.health,
        status: mon.status,
      },
    });
  }

  // Sort chronologically descending
  items.sort((a, b) => b.timestamp - a.timestamp);

  return items;
}

export function generateExplainabilityPayload(
  item: TimelineItem,
  snapshot: HostSnapshot
): ExplainabilityPayload {
  const permittedMetadata: Record<string, unknown> = {
    ...(item.payload || {}),
  };
  // Redact protected parameters if present in frontend payload
  delete permittedMetadata.sensitive_parameters;
  delete permittedMetadata.indicator_logic;
  delete permittedMetadata.lab_research;

  const permittedMarketContext = {
    symbol: snapshot.market?.symbol || "XAUUSD",
    timeframe: snapshot.market?.timeframe || "1h",
    status: snapshot.market?.status || "disconnected",
    provider: snapshot.market?.provider?.name || "None",
    lastPrice: snapshot.market?.quote?.last ?? snapshot.market?.quote?.mid ?? null,
  };

  const permittedRiskContext = {
    entryPrice: snapshot.risk?.entry || null,
    stopLoss: snapshot.risk?.stopLoss || null,
    takeProfits: snapshot.risk?.takeProfits || [],
    status: snapshot.risk?.status || "unavailable",
    riskRule: "1% Equity Risk Standard",
  };

  const explainabilityNotes = [
    `Context compiled from verified platform boundary '${item.source}'.`,
    "Articulates observed market quotes, provider states, and emitted signal metadata.",
    "Project 1 proprietary strategy math, indicators, and lab parameters remain protected.",
  ];

  if (!snapshot.security?.isAdmin) {
    explainabilityNotes.push(
      "Standard User Profile Active: Internal parameter weights and lab research are filtered."
    );
  }

  return {
    itemId: item.itemId,
    itemType: item.category,
    receivedAt: item.formattedTime,
    source: item.source,
    freshnessStatus: snapshot.monitoring?.freshness || "fresh",
    permittedMetadata,
    permittedMarketContext,
    permittedRiskContext,
    explainabilityNotes,
  };
}

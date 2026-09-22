import type { HostSnapshot } from "./hostView";

export type AlertKind = "freshness" | "price" | "signal" | "provider" | "security";
export type AlertSeverity = "info" | "warning" | "critical";
export type AlertStatus = "active" | "acknowledged" | "resolved";

export type ConditionType =
  | "price_above"
  | "price_below"
  | "signal_action"
  | "confidence_below"
  | "provider_disconnect";

export interface MarketAlertItem {
  id: string;
  kind: AlertKind;
  severity: AlertSeverity;
  status: AlertStatus;
  message: string;
  symbol: string;
  timeframe: string;
  createdAt: string;
  details?: Record<string, unknown>;
}

export interface AlertRuleConfig {
  ruleId: string;
  kind: AlertKind;
  symbol: string;
  conditionType: ConditionType;
  threshold?: number;
  expectedValue?: string;
  timeframe: string;
  enabled: boolean;
  createdAt: string;
}

const ALERTS_STORAGE_KEY_PREFIX = "ai_lab_platform_alerts_";
const RULES_STORAGE_KEY_PREFIX = "ai_lab_platform_alert_rules_";

export function loadUserAlerts(userId: string): MarketAlertItem[] {
  try {
    const raw = localStorage.getItem(`${ALERTS_STORAGE_KEY_PREFIX}${userId}`);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (err) {
    console.error("Failed to load user alerts:", err);
    return [];
  }
}

export function saveUserAlerts(userId: string, alerts: MarketAlertItem[]): void {
  try {
    localStorage.setItem(`${ALERTS_STORAGE_KEY_PREFIX}${userId}`, JSON.stringify(alerts));
  } catch (err) {
    console.error("Failed to save user alerts:", err);
  }
}

export function loadUserAlertRules(userId: string): AlertRuleConfig[] {
  try {
    const raw = localStorage.getItem(`${RULES_STORAGE_KEY_PREFIX}${userId}`);
    if (!raw) return createDefaultAlertRules("XAUUSD");
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.length > 0 ? parsed : createDefaultAlertRules("XAUUSD");
  } catch (err) {
    console.error("Failed to load user alert rules:", err);
    return createDefaultAlertRules("XAUUSD");
  }
}

export function saveUserAlertRules(userId: string, rules: AlertRuleConfig[]): void {
  try {
    localStorage.setItem(`${RULES_STORAGE_KEY_PREFIX}${userId}`, JSON.stringify(rules));
  } catch (err) {
    console.error("Failed to save user alert rules:", err);
  }
}

export function createDefaultAlertRules(symbol: string = "XAUUSD"): AlertRuleConfig[] {
  const now = new Date().toISOString();
  return [
    {
      ruleId: "default_price_high",
      kind: "price",
      symbol,
      conditionType: "price_above",
      threshold: 2750.0,
      timeframe: "1h",
      enabled: true,
      createdAt: now,
    },
    {
      ruleId: "default_price_low",
      kind: "price",
      symbol,
      conditionType: "price_below",
      threshold: 2550.0,
      timeframe: "1h",
      enabled: true,
      createdAt: now,
    },
    {
      ruleId: "default_signal_buy",
      kind: "signal",
      symbol,
      conditionType: "signal_action",
      expectedValue: "BUY",
      timeframe: "1h",
      enabled: true,
      createdAt: now,
    },
    {
      ruleId: "default_provider_disc",
      kind: "provider",
      symbol,
      conditionType: "provider_disconnect",
      timeframe: "1h",
      enabled: true,
      createdAt: now,
    },
  ];
}

export function countActiveAlerts(alerts: MarketAlertItem[]): number {
  return alerts.filter((a) => a.status === "active").length;
}

export function syncAlertsFromHostSnapshot(
  userId: string,
  snapshot: HostSnapshot,
  existingAlerts: MarketAlertItem[],
  rules: AlertRuleConfig[]
): MarketAlertItem[] {
  const newAlerts: MarketAlertItem[] = [...existingAlerts];
  const now = new Date().toISOString();

  // 1. Snapshot market freshness alert
  if (snapshot.market.status === "disconnected") {
    const alertId = `freshness_disc_${snapshot.market.symbol}`;
    if (!newAlerts.some((a) => a.id === alertId)) {
      newAlerts.unshift({
        id: alertId,
        kind: "freshness",
        severity: "critical",
        status: "active",
        message: `Market data provider is disconnected for ${snapshot.market.symbol}.`,
        symbol: snapshot.market.symbol,
        timeframe: snapshot.market.timeframe || "1h",
        createdAt: now,
        details: { status: snapshot.market.status },
      });
    }
  }

  // 2. Evaluate active user rules against snapshot data
  const price = snapshot.market.quote?.last ?? snapshot.market.quote?.mid ?? snapshot.market.quote?.bid ?? null;
  const signalAction = snapshot.signal.action || null;
  const confidence = snapshot.signal.confidence ?? null;

  for (const rule of rules) {
    if (!rule.enabled || rule.symbol !== snapshot.market.symbol) continue;

    if (rule.conditionType === "price_above" && rule.threshold != null && price != null && price >= rule.threshold) {
      const alertId = `rule_${rule.ruleId}_above_${Math.floor(price)}`;
      if (!newAlerts.some((a) => a.id === alertId)) {
        newAlerts.unshift({
          id: alertId,
          kind: rule.kind,
          severity: "warning",
          status: "active",
          message: `Price threshold reached: ${snapshot.market.symbol} price ${price.toFixed(2)} >= ${rule.threshold}`,
          symbol: rule.symbol,
          timeframe: rule.timeframe,
          createdAt: now,
          details: { observedPrice: price, threshold: rule.threshold },
        });
      }
    }

    if (rule.conditionType === "price_below" && rule.threshold != null && price != null && price <= rule.threshold) {
      const alertId = `rule_${rule.ruleId}_below_${Math.floor(price)}`;
      if (!newAlerts.some((a) => a.id === alertId)) {
        newAlerts.unshift({
          id: alertId,
          kind: rule.kind,
          severity: "warning",
          status: "active",
          message: `Price threshold reached: ${snapshot.market.symbol} price ${price.toFixed(2)} <= ${rule.threshold}`,
          symbol: rule.symbol,
          timeframe: rule.timeframe,
          createdAt: now,
          details: { observedPrice: price, threshold: rule.threshold },
        });
      }
    }

    if (rule.conditionType === "signal_action" && rule.expectedValue && signalAction) {
      if (signalAction.toUpperCase() === rule.expectedValue.toUpperCase() && signalAction.toUpperCase() !== "NO SIGNAL") {
        const alertId = `rule_${rule.ruleId}_sig_${signalAction.toLowerCase()}`;
        if (!newAlerts.some((a) => a.id === alertId)) {
          newAlerts.unshift({
            id: alertId,
            kind: rule.kind,
            severity: "info",
            status: "active",
            message: `New Project 1 ${signalAction.toUpperCase()} signal emitted for ${rule.symbol}.`,
            symbol: rule.symbol,
            timeframe: rule.timeframe,
            createdAt: now,
            details: { action: signalAction, confidence },
          });
        }
      }
    }

    if (rule.conditionType === "provider_disconnect" && !snapshot.project1.connected) {
      const alertId = `rule_${rule.ruleId}_p1_disc`;
      if (!newAlerts.some((a) => a.id === alertId)) {
        newAlerts.unshift({
          id: alertId,
          kind: rule.kind,
          severity: "critical",
          status: "active",
          message: `Project 1 engine is disconnected. Live signals are unavailable.`,
          symbol: rule.symbol,
          timeframe: rule.timeframe,
          createdAt: now,
          details: { port: snapshot.project1.port },
        });
      }
    }
  }

  saveUserAlerts(userId, newAlerts);
  return newAlerts;
}

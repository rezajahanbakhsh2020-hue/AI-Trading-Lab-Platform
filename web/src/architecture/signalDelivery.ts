import type { HostSnapshot } from "./hostView";

export type DeliveryChannelType = "telegram" | "webhook" | "in_app";
export type DeliveryStatus = "DELIVERED" | "NOT_DELIVERED" | "PENDING";

export interface OutboundChannelConfig {
  channelId: DeliveryChannelType;
  channelName: string;
  enabled: boolean;
  destination: string;
  status: "configured" | "unconfigured" | "error";
  requiresSetupPermission: boolean;
}

export interface SignalDeliveryRecord {
  id: string;
  timestamp: string;
  consumerId: string;
  symbol: string;
  action: string;
  channel: DeliveryChannelType;
  status: DeliveryStatus;
  reason: string;
  redacted: boolean;
  detail?: string;
}

export interface SignalDeliveryPolicy {
  consumerId: string;
  hasReadSignalsPermission: boolean;
  hasReadSetupPermission: boolean;
  deliveryEnabled: boolean;
  allowedSymbols: readonly string[];
  allowedStrategies: readonly string[];
}

const STORAGE_KEY = "ai_trading_lab_signal_deliveries_v1";

/**
  Evaluates whether a consumer is authorized to receive a signal for a symbol/strategy based on permissions and policy.
 */
export function evaluateDeliveryAuthorization(
  policy: SignalDeliveryPolicy,
  symbol: string,
  strategyName?: string | null
): { authorized: boolean; reason: string } {
  if (!policy.hasReadSignalsPermission) {
    return { authorized: false, reason: "consumer lacks READ_SIGNALS permission" };
  }
  if (!policy.deliveryEnabled) {
    return { authorized: false, reason: "signal delivery is disabled for consumer" };
  }
  if (
    policy.allowedSymbols.length > 0 &&
    !policy.allowedSymbols.includes(symbol.toUpperCase())
  ) {
    return { authorized: false, reason: `symbol ${symbol} not in consumer allowed symbols` };
  }
  if (
    policy.allowedStrategies.length > 0 &&
    strategyName &&
    !policy.allowedStrategies.includes(strategyName)
  ) {
    return { authorized: false, reason: `strategy ${strategyName} not in consumer allowed strategies` };
  }
  return { authorized: true, reason: "signal delivery authorized" };
}

/**
  Returns standard configured outbound channels for host snapshot.
 */
export function getSampleOutboundChannels(
  snapshot: HostSnapshot
): readonly OutboundChannelConfig[] {
  const isAdmin = snapshot.security?.isAdmin ?? false;
  return [
    {
      channelId: "telegram",
      channelName: "Telegram Bot Channel",
      enabled: true,
      destination: "@AITradingLabBot (chat_777)",
      status: "configured",
      requiresSetupPermission: false,
    },
    {
      channelId: "in_app",
      channelName: "In-App Signal Feed",
      enabled: true,
      destination: `User Inbox (${snapshot.security?.userId || "user_default"})`,
      status: "configured",
      requiresSetupPermission: false,
    },
    {
      channelId: "webhook",
      channelName: "Direct Outbound Webhook",
      enabled: isAdmin,
      destination: "https://api.tradingplatform.local/v1/webhook",
      status: isAdmin ? "configured" : "unconfigured",
      requiresSetupPermission: true,
    },
  ];
}

/**
  Performs an outbound signal delivery attempt for a given channel and consumer ID.
 */
export function executeSignalDeliveryDispatch(
  snapshot: HostSnapshot,
  channel: DeliveryChannelType,
  consumerId: string = "user_default"
): SignalDeliveryRecord {
  const timestamp = new Date().toUTCString();
  const id = `del_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;

  if (!snapshot.project1.connected) {
    return {
      id,
      timestamp,
      consumerId,
      symbol: snapshot.market.symbol,
      action: snapshot.signal.action || "NO SIGNAL",
      channel,
      status: "NOT_DELIVERED",
      reason: "Project 1 engine disconnected. Signal delivery held.",
      redacted: false,
      detail: "No active signal connection.",
    };
  }

  if (!snapshot.signal.action || snapshot.signal.action === "NO SIGNAL") {
    return {
      id,
      timestamp,
      consumerId,
      symbol: snapshot.market.symbol,
      action: "NO SIGNAL",
      channel,
      status: "NOT_DELIVERED",
      reason: "No active signal emitted by Project 1.",
      redacted: false,
      detail: "Action holds on NO SIGNAL.",
    };
  }

  const permissions = snapshot.security?.permissions ?? ["read:signals"];
  const isAdmin = snapshot.security?.isAdmin ?? false;
  const hasSetupPerm = isAdmin || permissions.includes("read:trade_setups");

  const policy: SignalDeliveryPolicy = {
    consumerId,
    hasReadSignalsPermission: isAdmin || permissions.includes("read:signals"),
    hasReadSetupPermission: hasSetupPerm,
    deliveryEnabled: true,
    allowedSymbols: ["XAUUSD", "EURUSD", "GBPUSD", "BTCUSD", "SPX500"],
    allowedStrategies: [],
  };

  const evalRes = evaluateDeliveryAuthorization(
    policy,
    snapshot.market.symbol,
    snapshot.strategy.name
  );

  if (!evalRes.authorized) {
    return {
      id,
      timestamp,
      consumerId,
      symbol: snapshot.market.symbol,
      action: snapshot.signal.action,
      channel,
      status: "NOT_DELIVERED",
      reason: evalRes.reason,
      redacted: !hasSetupPerm,
      detail: "Authorization denied by security boundary policy.",
    };
  }

  const isRedacted = !hasSetupPerm;
  const detail = isRedacted
    ? `Delivered to ${channel}. Trade setup entry/SL levels masked for restricted user role.`
    : `Delivered successfully to ${channel} with full trade geometry setup.`;

  return {
    id,
    timestamp,
    consumerId,
    symbol: snapshot.market.symbol,
    action: snapshot.signal.action,
    channel,
    status: "DELIVERED",
    reason: "Signal delivered successfully",
    redacted: isRedacted,
    detail,
  };
}

/**
  Loads stored delivery records for user.
 */
export function loadSignalDeliveryHistory(consumerId: string): SignalDeliveryRecord[] {
  try {
    const raw = localStorage.getItem(`${STORAGE_KEY}_${consumerId}`);
    if (!raw) return [];
    return JSON.parse(raw) as SignalDeliveryRecord[];
  } catch {
    return [];
  }
}

/**
  Saves delivery record to history.
 */
export function saveSignalDeliveryRecord(
  consumerId: string,
  record: SignalDeliveryRecord
): SignalDeliveryRecord[] {
  const existing = loadSignalDeliveryHistory(consumerId);
  const updated = [record, ...existing].slice(0, 50);
  try {
    localStorage.setItem(`${STORAGE_KEY}_${consumerId}`, JSON.stringify(updated));
  } catch {
    // Ignore storage error
  }
  return updated;
}

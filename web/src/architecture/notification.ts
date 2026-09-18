import type { HostSnapshot } from "./hostView";

export type NotificationCategory =
  | "all"
  | "signal"
  | "project1_integration"
  | "signal_lifecycle"
  | "market_health"
  | "workspace"
  | "system"
  | "security"
  | "account_session"
  | "admin";

export type NotificationSeverity = "info" | "success" | "warning" | "error";

export interface NotificationPreferencesClient {
  enabled_categories: string[];
  in_app_enabled: boolean;
  external_delivery_enabled: boolean;
  min_severity: string;
}

export interface DeliveryChannelStatus {
  status: "IN_APP_AVAILABLE" | "EXTERNAL_CONFIGURED" | "EXTERNAL_NOT_CONFIGURED" | "DELIVERY_FAILED" | "DELIVERY_UNAVAILABLE";
  configured: boolean;
  chat_id?: string | null;
}

export interface NotificationItem {
  id: string;
  userId: string;
  category: NotificationCategory;
  severity: NotificationSeverity;
  title: string;
  message: string;
  timestamp: string;
  rawTimestamp: number;
  read: boolean;
  archived: boolean;
  metadata?: Record<string, unknown>;
}

export const NOTIFICATION_STORAGE_KEY_PREFIX = "ai_trading_lab_notifications_";

// Memory fallback store when window.localStorage is unavailable (e.g. node environment)
const inMemoryStore: Record<string, string> = {};

function getStorageItem(key: string): string | null {
  if (typeof window !== "undefined" && window.localStorage) {
    try {
      return localStorage.getItem(key);
    } catch {
      return inMemoryStore[key] || null;
    }
  }
  return inMemoryStore[key] || null;
}

function setStorageItem(key: string, value: string): void {
  if (typeof window !== "undefined" && window.localStorage) {
    try {
      localStorage.setItem(key, value);
    } catch {
      inMemoryStore[key] = value;
    }
  } else {
    inMemoryStore[key] = value;
  }
}

/**
 * Load notifications for a specific user.
 */
export function loadUserNotifications(userId: string): NotificationItem[] {
  try {
    const raw = getStorageItem(`${NOTIFICATION_STORAGE_KEY_PREFIX}${userId}`);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed;
  } catch {
    return [];
  }
}

/**
 * Save notifications for a specific user.
 */
export function saveUserNotifications(userId: string, notifications: NotificationItem[]): void {
  try {
    setStorageItem(
      `${NOTIFICATION_STORAGE_KEY_PREFIX}${userId}`,
      JSON.stringify(notifications)
    );
  } catch {
    // Ignore storage quota errors
  }
}

/**
 * Sync real notifications from HostSnapshot state into user inbox without duplicating existing notifications.
 */
export function syncNotificationsFromHostSnapshot(
  userId: string,
  snapshot: HostSnapshot,
  existingNotifications: NotificationItem[]
): NotificationItem[] {
  const newItems: NotificationItem[] = [];
  const now = Date.now();
  const timeStr = new Date(now).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  // 1. Signal notification from snapshot
  if (snapshot.project1.connected && snapshot.signal.action && snapshot.signal.action !== "NO SIGNAL") {
    const sigId = snapshot.signal.signalId || `sig_${snapshot.market.symbol}_${snapshot.signal.action}`;
    const notifId = `notif_snapshot_sig_${sigId}`;
    if (!existingNotifications.some((n) => n.id === notifId)) {
      newItems.push({
        id: notifId,
        userId,
        category: "signal",
        severity: "info",
        title: `Project 1 Signal Emitted (${snapshot.signal.action})`,
        message: `Validated ${snapshot.signal.action} signal for ${snapshot.market.symbol} (${snapshot.signal.strategyName || "Strategy"}).`,
        timestamp: snapshot.signal.timestamp || timeStr,
        rawTimestamp: now,
        read: false,
        archived: false,
        metadata: {
          symbol: snapshot.market.symbol,
          action: snapshot.signal.action,
          strategy: snapshot.signal.strategyName,
        },
      });
    }
  } else if (!snapshot.project1.connected) {
    const notifId = `notif_snapshot_p1_disconnected`;
    if (!existingNotifications.some((n) => n.id === notifId)) {
      newItems.push({
        id: notifId,
        userId,
        category: "system",
        severity: "warning",
        title: "Project 1 Disconnected",
        message: "Project 1 engine is disconnected. Displaying honest unavailable state.",
        timestamp: timeStr,
        rawTimestamp: now,
        read: false,
        archived: false,
      });
    }
  }

  // 2. Provider health notification
  if (snapshot.market.status === "connected" && snapshot.market.provider) {
    const notifId = `notif_snapshot_provider_${snapshot.market.provider.name}`;
    if (!existingNotifications.some((n) => n.id === notifId)) {
      newItems.push({
        id: notifId,
        userId,
        category: "market_health",
        severity: "success",
        title: `Market Data Provider Active (${snapshot.market.provider.name})`,
        message: `Connected to market provider ${snapshot.market.provider.name} streaming candles.`,
        timestamp: timeStr,
        rawTimestamp: now,
        read: false,
        archived: false,
      });
    }
  } else if (snapshot.market.status === "disconnected") {
    const notifId = `notif_snapshot_provider_disconnected`;
    if (!existingNotifications.some((n) => n.id === notifId)) {
      newItems.push({
        id: notifId,
        userId,
        category: "market_health",
        severity: "warning",
        title: "Market Data Provider Disconnected",
        message: "No market data provider attached. Connect provider to stream live market quotes.",
        timestamp: timeStr,
        rawTimestamp: now,
        read: false,
        archived: false,
      });
    }
  }

  if (newItems.length === 0) {
    return existingNotifications;
  }

  const merged = [...newItems, ...existingNotifications];
  // Sort newest first
  merged.sort((a, b) => b.rawTimestamp - a.rawTimestamp);
  return merged;
}

/**
 * Filter notifications by category tab and read/archived status.
 */
export function filterNotifications(
  notifications: NotificationItem[],
  category: NotificationCategory = "all",
  includeArchived: boolean = false
): NotificationItem[] {
  return notifications.filter((n) => {
    if (!includeArchived && n.archived) return false;
    if (category !== "all" && n.category !== category) return false;
    return true;
  });
}

/**
 * Calculate unread count for non-archived notifications.
 */
export function countUnreadNotifications(notifications: NotificationItem[]): number {
  return notifications.filter((n) => !n.read && !n.archived).length;
}

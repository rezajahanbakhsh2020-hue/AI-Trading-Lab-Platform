import { useState, useMemo } from "react";
import {
  countUnreadNotifications,
  filterNotifications,
  type NotificationCategory,
  type NotificationItem,
} from "../../architecture/notification";
import { useI18n } from "../../i18n";
import { EmptyState } from "./EmptyState";

interface NotificationCenterProps {
  notifications: NotificationItem[];
  onMarkRead: (id: string) => void;
  onMarkAllRead: () => void;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
}

export function NotificationCenter({
  notifications,
  onMarkRead,
  onMarkAllRead,
  onArchive,
  onDelete,
}: NotificationCenterProps) {
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState<NotificationCategory>("all");
  const [showArchived, setShowArchived] = useState(false);

  const unreadCount = useMemo(() => countUnreadNotifications(notifications), [notifications]);

  const filteredNotifications = useMemo(() => {
    return filterNotifications(notifications, activeTab, showArchived);
  }, [notifications, activeTab, showArchived]);

  const tabs: { key: NotificationCategory; label: string }[] = [
    { key: "all", label: t("notifications.tabs.all") },
    { key: "signal", label: t("notifications.tabs.signal") },
    { key: "market_health", label: t("notifications.tabs.market_health") },
    { key: "workspace", label: t("notifications.tabs.workspace") },
    { key: "system", label: t("notifications.tabs.system") },
  ];

  const getSeverityBadgeClass = (severity: string) => {
    switch (severity) {
      case "success":
        return "status ready";
      case "warning":
        return "status warn";
      case "error":
        return "status disconnected";
      default:
        return "status";
    }
  };

  return (
    <div className="notification-center-widget">
      <div className="card">
        <div className="card-head" style={{ flexWrap: "wrap", gap: 12 }}>
          <div>
            <h3>{t("notifications.feedTitle")}</h3>
            <p className="hint">{t("notifications.feedSub")}</p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            {unreadCount > 0 && (
              <span className="chip ready-chip">
                {t("notifications.unreadBadge", { count: unreadCount })}
              </span>
            )}
            <button
              className="btn btn-secondary"
              onClick={() => setShowArchived((prev) => !prev)}
              style={{ fontSize: 13, padding: "6px 12px" }}
            >
              {showArchived
                ? t("notifications.actions.hideArchived")
                : t("notifications.actions.showArchived")}
            </button>
            <button
              className="btn btn-primary"
              onClick={onMarkAllRead}
              disabled={unreadCount === 0}
              style={{ fontSize: 13, padding: "6px 12px" }}
            >
              {t("buttons.markAllRead")}
            </button>
          </div>
        </div>

        <div className="card-body">
          {/* Category Filter Tabs */}
          <div className="notification-tabs" style={{ display: "flex", gap: 8, marginBottom: 16, overflowX: "auto" }}>
            {tabs.map((tab) => (
              <button
                key={tab.key}
                className={`btn ${activeTab === tab.key ? "btn-primary" : "btn-secondary"}`}
                onClick={() => setActiveTab(tab.key)}
                style={{ fontSize: 13, padding: "6px 14px", whiteSpace: "nowrap" }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Privacy Note */}
          <div className="privacy-note-box" style={{ marginBottom: 16, padding: "10px 14px", borderRadius: 6, background: "rgba(255, 255, 255, 0.03)", borderLeft: "3px solid #3b82f6" }}>
            <span style={{ fontSize: 12, opacity: 0.85 }}>
              🛡️ {t("notifications.privacyNote")}
            </span>
          </div>

          {/* List or Empty State */}
          {filteredNotifications.length === 0 ? (
            <EmptyState
              title={t("notifications.emptyState.title")}
              message={t("notifications.emptyState.sub")}
            />
          ) : (
            <div className="notifications-list" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {filteredNotifications.map((n) => (
                <div
                  key={n.id}
                  className={`notif-item ${n.read ? "read" : "unread"} ${n.archived ? "archived" : ""}`}
                  style={{
                    padding: "14px",
                    borderRadius: 8,
                    background: n.read ? "var(--card-bg, rgba(255,255,255,0.02))" : "rgba(59, 130, 246, 0.08)",
                    border: n.read ? "1px solid rgba(255,255,255,0.05)" : "1px solid rgba(59, 130, 246, 0.3)",
                    transition: "all 0.2s ease",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      <span className={getSeverityBadgeClass(n.severity)}>
                        {n.category.toUpperCase()}
                      </span>
                      <strong className="notif-title" style={{ fontSize: 14 }}>
                        {n.title}
                      </strong>
                      {!n.read && <span className="dot ready" style={{ width: 8, height: 8 }} />}
                    </div>
                    <span className="notif-time" style={{ fontSize: 12, opacity: 0.65, whiteSpace: "nowrap" }}>
                      {n.timestamp}
                    </span>
                  </div>

                  <p className="hint" style={{ marginTop: 8, fontSize: 13, lineHeight: 1.4 }}>
                    {n.message}
                  </p>

                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 10 }}>
                    {!n.read && (
                      <button
                        className="btn btn-secondary notif-btn-mark-read"
                        onClick={() => onMarkRead(n.id)}
                        style={{ fontSize: 11, padding: "4px 8px" }}
                      >
                        {t("notifications.actions.markRead")}
                      </button>
                    )}
                    {!n.archived && (
                      <button
                        className="btn btn-secondary notif-btn-archive"
                        onClick={() => onArchive(n.id)}
                        style={{ fontSize: 11, padding: "4px 8px" }}
                      >
                        {t("notifications.actions.archive")}
                      </button>
                    )}
                    <button
                      className="btn btn-secondary notif-btn-delete"
                      onClick={() => onDelete(n.id)}
                      style={{ fontSize: 11, padding: "4px 8px", opacity: 0.7 }}
                    >
                      {t("notifications.actions.delete")}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { NotificationCenter } from "./NotificationCenter";
import { I18nProvider } from "../../i18n";
import type { NotificationItem } from "../../architecture/notification";

const sampleNotifications: NotificationItem[] = [
  {
    id: "n1",
    userId: "user_1",
    category: "signal",
    severity: "info",
    title: "BUY Signal Emitted",
    message: "Validated BUY signal for XAUUSD.",
    timestamp: "10:30 AM",
    rawTimestamp: 1000,
    read: false,
    archived: false,
  },
  {
    id: "n2",
    userId: "user_1",
    category: "market_health",
    severity: "success",
    title: "Market Provider Active",
    message: "Connected to BiQuoteProvider.",
    timestamp: "10:25 AM",
    rawTimestamp: 900,
    read: true,
    archived: false,
  },
];

describe("NotificationCenter UI Component", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders notifications list and unread badge in English (LTR)", () => {
    render(
      <I18nProvider>
        <NotificationCenter
          notifications={sampleNotifications}
          onMarkRead={() => {}}
          onMarkAllRead={() => {}}
          onArchive={() => {}}
          onDelete={() => {}}
        />
      </I18nProvider>
    );

    expect(screen.getByText("Notification Center")).toBeDefined();
    expect(screen.getByText("BUY Signal Emitted")).toBeDefined();
    expect(screen.getByText("1 Unread")).toBeDefined();
  });

  it("renders notifications in Persian (FA, RTL)", () => {
    localStorage.setItem("ai_trading_lab_lang", "fa");
    render(
      <I18nProvider>
        <NotificationCenter
          notifications={sampleNotifications}
          onMarkRead={() => {}}
          onMarkAllRead={() => {}}
          onArchive={() => {}}
          onDelete={() => {}}
        />
      </I18nProvider>
    );

    expect(screen.getByText("مرکز اعلان‌ها")).toBeDefined();
    expect(screen.getByText("1 خوانده‌نشده")).toBeDefined();
  });

  it("triggers markRead, archive, and delete action callbacks", () => {
    let markedId = "";
    let archivedId = "";
    let deletedId = "";

    const singleUnreadNotification: NotificationItem[] = [
      {
        id: "n1",
        userId: "user_1",
        category: "signal",
        severity: "info",
        title: "BUY Signal Emitted",
        message: "Validated BUY signal for XAUUSD.",
        timestamp: "10:30 AM",
        rawTimestamp: 1000,
        read: false,
        archived: false,
      },
    ];

    const { container } = render(
      <I18nProvider>
        <NotificationCenter
          notifications={singleUnreadNotification}
          onMarkRead={(id) => { markedId = id; }}
          onMarkAllRead={() => {}}
          onArchive={(id) => { archivedId = id; }}
          onDelete={(id) => { deletedId = id; }}
        />
      </I18nProvider>
    );

    const markReadBtn = container.querySelector(".notif-btn-mark-read");
    expect(markReadBtn).not.toBeNull();
    if (markReadBtn) fireEvent.click(markReadBtn);
    expect(markedId).toBe("n1");

    const archiveBtn = container.querySelector(".notif-btn-archive");
    expect(archiveBtn).not.toBeNull();
    if (archiveBtn) fireEvent.click(archiveBtn);
    expect(archivedId).toBe("n1");

    const deleteBtn = container.querySelector(".notif-btn-delete");
    expect(deleteBtn).not.toBeNull();
    if (deleteBtn) fireEvent.click(deleteBtn);
    expect(deletedId).toBe("n1");
  });
});

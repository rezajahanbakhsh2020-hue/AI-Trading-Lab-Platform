import { describe, it, expect } from "vitest";
import {
  countUnreadNotifications,
  filterNotifications,
  loadUserNotifications,
  saveUserNotifications,
  syncNotificationsFromHostSnapshot,
  type NotificationItem,
} from "./notification";
import {
  createDisconnectedHostSnapshot,
  createHostSnapshotFromProject1,
  SAMPLE_CONNECTED_PORT,
  SAMPLE_REAL_PROJECT1_SIGNAL,
} from "./hostView";

describe("Notification Architecture & Store", () => {
  it("persists and loads notifications per user_id with isolation", () => {
    const user1Notifs: NotificationItem[] = [
      {
        id: "n1",
        userId: "user_1",
        category: "signal",
        severity: "info",
        title: "User 1 Signal",
        message: "BUY XAUUSD",
        timestamp: "10:00 AM",
        rawTimestamp: 1000,
        read: false,
        archived: false,
      },
    ];

    saveUserNotifications("user_1", user1Notifs);

    expect(loadUserNotifications("user_1")).toEqual(user1Notifs);
    expect(loadUserNotifications("user_2")).toEqual([]);
  });

  it("syncs notifications from disconnected host snapshot without duplicates", () => {
    const snap = createDisconnectedHostSnapshot("XAUUSD", "1h");
    const synced = syncNotificationsFromHostSnapshot("user_snapshot_test", snap, []);

    expect(synced.length).toBeGreaterThan(0);
    expect(synced.some((n) => n.title.includes("Disconnected"))).toBe(true);

    // Syncing again should not add duplicate IDs
    const synced2 = syncNotificationsFromHostSnapshot("user_snapshot_test", snap, synced);
    expect(synced2.length).toBe(synced.length);
  });

  it("syncs notifications from connected Project 1 host snapshot", () => {
    const snap = createHostSnapshotFromProject1(
      SAMPLE_CONNECTED_PORT,
      SAMPLE_REAL_PROJECT1_SIGNAL,
      "XAUUSD",
      "1h"
    );
    const synced = syncNotificationsFromHostSnapshot("user_connected_test", snap, []);

    expect(synced.some((n) => n.category === "signal" && n.title.includes("BUY"))).toBe(true);
  });

  it("filters notifications by category and archived status", () => {
    const items: NotificationItem[] = [
      {
        id: "1",
        userId: "u1",
        category: "signal",
        severity: "info",
        title: "Sig",
        message: "M",
        timestamp: "10:00",
        rawTimestamp: 1,
        read: false,
        archived: false,
      },
      {
        id: "2",
        userId: "u1",
        category: "system",
        severity: "warning",
        title: "Sys",
        message: "M",
        timestamp: "10:01",
        rawTimestamp: 2,
        read: true,
        archived: false,
      },
      {
        id: "3",
        userId: "u1",
        category: "signal",
        severity: "info",
        title: "Archived Sig",
        message: "M",
        timestamp: "10:02",
        rawTimestamp: 3,
        read: true,
        archived: true,
      },
    ];

    const activeSignals = filterNotifications(items, "signal", false);
    expect(activeSignals.length).toBe(1);
    expect(activeSignals[0].id).toBe("1");

    const allSignalsWithArchived = filterNotifications(items, "signal", true);
    expect(allSignalsWithArchived.length).toBe(2);

    const activeAll = filterNotifications(items, "all", false);
    expect(activeAll.length).toBe(2);
  });

  it("counts unread non-archived notifications correctly", () => {
    const items: NotificationItem[] = [
      {
        id: "1",
        userId: "u1",
        category: "signal",
        severity: "info",
        title: "Sig",
        message: "M",
        timestamp: "10:00",
        rawTimestamp: 1,
        read: false,
        archived: false,
      },
      {
        id: "2",
        userId: "u1",
        category: "system",
        severity: "warning",
        title: "Sys",
        message: "M",
        timestamp: "10:01",
        rawTimestamp: 2,
        read: true,
        archived: false,
      },
      {
        id: "3",
        userId: "u1",
        category: "signal",
        severity: "info",
        title: "Archived Unread",
        message: "M",
        timestamp: "10:02",
        rawTimestamp: 3,
        read: false,
        archived: true,
      },
    ];

    expect(countUnreadNotifications(items)).toBe(1);
  });
});

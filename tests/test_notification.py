"""Tests for Notification and NotificationEvent domain models and NotificationService application layer."""

import pytest
import time

from src.platform.domain.notification import (
    Notification,
    NotificationCategory,
    NotificationEvent,
    NotificationSeverity,
)
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.notification import (
    InMemoryNotificationRepository,
    NotificationService,
)
from src.platform.services.security import SecurityBoundaryService


def test_notification_domain_validation_and_immutability():
    ts = time.time()
    notif = Notification(
        notification_id="n1",
        user_id="user_1",
        category=NotificationCategory.SIGNAL,
        severity=NotificationSeverity.INFO,
        title="Signal Alert",
        message="BUY XAUUSD emitted",
        timestamp=ts,
        is_read=False,
        is_archived=False,
        metadata={"symbol": "XAUUSD"},
    )

    assert notif.notification_id == "n1"
    assert notif.user_id == "user_1"
    assert notif.category == NotificationCategory.SIGNAL
    assert notif.severity == NotificationSeverity.INFO
    assert notif.is_read is False
    assert notif.is_archived is False
    assert notif.metadata == {"symbol": "XAUUSD"}

    # Test immutability
    with pytest.raises(AttributeError):
        notif.is_read = True

    # Test with_read and with_archived
    read_notif = notif.with_read(True)
    assert read_notif.is_read is True
    assert notif.is_read is False  # Original unchanged

    archived_notif = notif.with_archived(True)
    assert archived_notif.is_archived is True
    assert notif.is_archived is False

    # Test to_dict
    d = notif.to_dict()
    assert d["notification_id"] == "n1"
    assert d["category"] == "signal"
    assert d["severity"] == "info"


def test_notification_event_validation():
    ts = time.time()
    evt = NotificationEvent(
        event_id="evt_1",
        event_type="SIGNAL_EMITTED",
        category="signal",
        severity="info",
        title="Signal Alert",
        message="BUY XAUUSD",
        timestamp=ts,
        target_user_id="user_1",
        payload={"action": "buy"},
    )
    assert evt.event_id == "evt_1"
    assert evt.category == NotificationCategory.SIGNAL
    assert evt.severity == NotificationSeverity.INFO

    with pytest.raises(ValueError):
        NotificationEvent(
            event_id="",
            event_type="TEST",
            category="invalid_category",
            severity="info",
            title="Title",
            message="Msg",
            timestamp=ts,
        )


def test_in_memory_repository_crud():
    repo = InMemoryNotificationRepository()
    ts = time.time()
    n1 = Notification(
        notification_id="n1",
        user_id="u1",
        category=NotificationCategory.SIGNAL,
        severity=NotificationSeverity.INFO,
        title="T1",
        message="M1",
        timestamp=ts,
    )
    n2 = Notification(
        notification_id="n2",
        user_id="u1",
        category=NotificationCategory.SYSTEM,
        severity=NotificationSeverity.WARNING,
        title="T2",
        message="M2",
        timestamp=ts + 10,
    )

    repo.save(n1)
    repo.save(n2)

    notifs = repo.get_notifications("u1")
    assert len(notifs) == 2
    assert notifs[0].notification_id == "n2"  # Newest first

    assert repo.get_by_id("u1", "n1") == n1
    assert repo.get_by_id("u1", "n99") is None

    assert repo.delete("u1", "n1") is True
    assert repo.get_by_id("u1", "n1") is None
    assert len(repo.get_notifications("u1")) == 1

    repo.clear()
    assert len(repo.get_notifications("u1")) == 0


def test_notification_service_user_isolation_and_authorization():
    sec_svc = SecurityBoundaryService()
    repo = InMemoryNotificationRepository()
    svc = NotificationService(repository=repo, security_service=sec_svc)

    user_a = UserAuthorization(
        user_id="user_a",
        auth_code="auth_a",
        role=UserRole.USER,
        permissions=[Permission.READ_SIGNALS],
    )
    user_b = UserAuthorization(
        user_id="user_b",
        auth_code="auth_b",
        role=UserRole.USER,
        permissions=[Permission.READ_SIGNALS],
    )
    admin_user = UserAuthorization(
        user_id="admin_1",
        auth_code="auth_admin",
        role=UserRole.ADMIN,
        permissions=[Permission.ADMIN_ALL],
    )

    # User A creates notification for User A
    n_a = svc.create_notification(
        requester=user_a,
        target_user_id="user_a",
        category=NotificationCategory.SIGNAL,
        severity=NotificationSeverity.INFO,
        title="User A Signal",
        message="BUY XAUUSD",
    )
    assert n_a.user_id == "user_a"

    # User A cannot read User B's notifications
    with pytest.raises(PermissionError):
        svc.get_notifications(requester=user_a, target_user_id="user_b")

    # User A cannot mark read or archive User B's notification
    svc.create_notification(
        requester=admin_user,
        target_user_id="user_b",
        category=NotificationCategory.SYSTEM,
        severity=NotificationSeverity.WARNING,
        title="User B System",
        message="Warning msg",
    )

    notifs_b = svc.get_notifications(requester=user_b, target_user_id="user_b")
    assert len(notifs_b) == 1
    n_b_id = notifs_b[0].notification_id

    with pytest.raises(PermissionError):
        svc.mark_as_read(requester=user_a, target_user_id="user_b", notification_id=n_b_id)

    # Admin CAN read and manage User B's notifications
    admin_notifs_b = svc.get_notifications(requester=admin_user, target_user_id="user_b")
    assert len(admin_notifs_b) == 1

    # Unauthenticated requester fails
    with pytest.raises(PermissionError):
        svc.get_notifications(requester=None, target_user_id="user_a")


def test_notification_service_secret_sanitization_and_privacy():
    svc = NotificationService()
    user = UserAuthorization(
        user_id="user_1",
        auth_code="auth_1",
        role=UserRole.USER,
        permissions=[Permission.READ_SIGNALS],
    )

    # Create notification with sensitive strings and metadata
    n = svc.create_notification(
        requester=user,
        target_user_id="user_1",
        category=NotificationCategory.SYSTEM,
        severity=NotificationSeverity.INFO,
        title="System Event token=secret_abc_12345",
        message="Connected with api_key=my_super_secret_key",
        metadata={
            "public_info": "ok",
            "api_key": "super_secret_123",
            "lab_secrets": {"hidden": "value"},
            "best_strategies": ["Protected Strategy A"],
        },
    )

    # Title & message sanitized
    assert "secret_abc_12345" not in n.title
    assert "[REDACTED]" in n.title
    assert "my_super_secret_key" not in n.message
    assert "[REDACTED]" in n.message

    # Retrieved notification sanitizes metadata for non-admin user
    retrieved = svc.get_notifications(requester=user, target_user_id="user_1")[0]
    assert retrieved.metadata.get("public_info") == "ok"
    assert retrieved.metadata.get("api_key") == "[REDACTED]"
    assert "lab_secrets" not in retrieved.metadata or retrieved.metadata.get("lab_secrets") == "[REDACTED]"
    assert "best_strategies" not in retrieved.metadata


def test_notification_service_read_archive_delete_operations():
    svc = NotificationService()
    user = UserAuthorization(
        user_id="user_1",
        auth_code="auth_1",
        role=UserRole.USER,
        permissions=[Permission.READ_SIGNALS],
    )

    n1 = svc.create_notification(
        requester=user,
        target_user_id="user_1",
        category=NotificationCategory.SIGNAL,
        severity=NotificationSeverity.INFO,
        title="Signal 1",
        message="Msg 1",
    )
    n2 = svc.create_notification(
        requester=user,
        target_user_id="user_1",
        category=NotificationCategory.MARKET_HEALTH,
        severity=NotificationSeverity.SUCCESS,
        title="Health 1",
        message="Msg 2",
    )

    assert svc.get_unread_count(user, "user_1") == 2

    # Mark as read
    svc.mark_as_read(user, "user_1", n1.notification_id)
    assert svc.get_unread_count(user, "user_1") == 1

    # Filter unread only
    unread = svc.get_notifications(user, "user_1", unread_only=True)
    assert len(unread) == 1
    assert unread[0].notification_id == n2.notification_id

    # Filter by category
    signals = svc.get_notifications(user, "user_1", category=NotificationCategory.SIGNAL)
    assert len(signals) == 1
    assert signals[0].notification_id == n1.notification_id

    # Mark all read
    marked = svc.mark_all_as_read(user, "user_1")
    assert marked == 1
    assert svc.get_unread_count(user, "user_1") == 0

    # Archive notification
    svc.archive_notification(user, "user_1", n1.notification_id)

    # Archived hidden by default
    active_notifs = svc.get_notifications(user, "user_1", include_archived=False)
    assert len(active_notifs) == 1

    # Include archived
    all_notifs = svc.get_notifications(user, "user_1", include_archived=True)
    assert len(all_notifs) == 2

    # Delete notification
    deleted = svc.delete_notification(user, "user_1", n2.notification_id)
    assert deleted is True
    assert len(svc.get_notifications(user, "user_1", include_archived=True)) == 1


def test_notification_service_real_host_events_mapping():
    svc = NotificationService()
    user = UserAuthorization(
        user_id="user_1",
        auth_code="auth_1",
        role=UserRole.USER,
        permissions=[Permission.READ_SIGNALS],
    )

    # Connected host mapping
    ts = time.time()
    notifs_connected = svc.map_real_host_events(
        requester=user,
        target_user_id="user_1",
        project1_connected=True,
        signal_action="BUY",
        signal_symbol="XAUUSD",
        provider_status="connected",
        provider_name="BiQuoteProvider",
        timestamp=ts,
    )
    assert len(notifs_connected) == 2
    assert notifs_connected[0].category == NotificationCategory.SIGNAL
    assert "BUY" in notifs_connected[0].title
    assert notifs_connected[1].category == NotificationCategory.MARKET_HEALTH

    # Disconnected host mapping
    notifs_disconnected = svc.map_real_host_events(
        requester=user,
        target_user_id="user_1",
        project1_connected=False,
        signal_action=None,
        signal_symbol=None,
        provider_status="disconnected",
        provider_name=None,
        timestamp=ts + 10,
    )
    assert len(notifs_disconnected) == 2
    assert notifs_disconnected[0].category == NotificationCategory.SYSTEM
    assert "Disconnected" in notifs_disconnected[0].title
    assert notifs_disconnected[1].severity == NotificationSeverity.WARNING

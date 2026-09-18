"""Notification application service, repository port, and in-memory adapter.

Implements Hexagonal Architecture port (NotificationRepositoryPort), in-memory adapter
(InMemoryNotificationRepository), and application service (NotificationService) with
security boundary authorization, secret sanitization, permission enforcement, and user isolation.
"""

from abc import ABC, abstractmethod
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

from src.platform.domain.notification import (
    Notification,
    NotificationCategory,
    NotificationEvent,
    NotificationSeverity,
)
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.security import SecretSanitizer, SecurityBoundaryService


class NotificationRepositoryPort(ABC):
    """Port interface for persisting and retrieving user notifications."""

    @abstractmethod
    def get_notifications(self, user_id: str) -> List[Notification]:
        """Retrieve all notifications for a given user_id."""
        pass

    @abstractmethod
    def get_by_id(self, user_id: str, notification_id: str) -> Optional[Notification]:
        """Retrieve a specific notification by ID for a given user_id."""
        pass

    @abstractmethod
    def save(self, notification: Notification) -> Notification:
        """Save or update a notification."""
        pass

    @abstractmethod
    def delete(self, user_id: str, notification_id: str) -> bool:
        """Delete a notification by ID for a user."""
        pass


class InMemoryNotificationRepository(NotificationRepositoryPort):
    """In-memory implementation of NotificationRepositoryPort."""

    def __init__(self) -> None:
        # Internal storage: user_id -> {notification_id: Notification}
        self._store: Dict[str, Dict[str, Notification]] = {}

    def get_notifications(self, user_id: str) -> List[Notification]:
        if not isinstance(user_id, str) or not user_id.strip():
            return []
        clean_uid = user_id.strip()
        user_store = self._store.get(clean_uid, {})
        # Return sorted by timestamp descending
        return sorted(user_store.values(), key=lambda n: n.timestamp, reverse=True)

    def get_by_id(self, user_id: str, notification_id: str) -> Optional[Notification]:
        if not isinstance(user_id, str) or not user_id.strip():
            return None
        if not isinstance(notification_id, str) or not notification_id.strip():
            return None
        clean_uid = user_id.strip()
        clean_nid = notification_id.strip()
        return self._store.get(clean_uid, {}).get(clean_nid)

    def save(self, notification: Notification) -> Notification:
        if not isinstance(notification, Notification):
            raise ValueError("notification must be a Notification instance")
        uid = notification.user_id
        if uid not in self._store:
            self._store[uid] = {}
        self._store[uid][notification.notification_id] = notification
        return notification

    def delete(self, user_id: str, notification_id: str) -> bool:
        if not isinstance(user_id, str) or not user_id.strip():
            return False
        if not isinstance(notification_id, str) or not notification_id.strip():
            return False
        clean_uid = user_id.strip()
        clean_nid = notification_id.strip()
        if clean_uid in self._store and clean_nid in self._store[clean_uid]:
            del self._store[clean_uid][clean_nid]
            return True
        return False

    def clear(self) -> None:
        """Clear all stored notifications."""
        self._store.clear()


class NotificationService:
    """Application service for user-scoped notification inbox management, authorization, and event mapping."""

    def __init__(
        self,
        repository: Optional[NotificationRepositoryPort] = None,
        security_service: Optional[SecurityBoundaryService] = None,
        workspace_service: Optional[Any] = None,
    ) -> None:
        self._repo = repository or InMemoryNotificationRepository()
        self._security = security_service or SecurityBoundaryService()
        self._workspace_service = workspace_service

    def _authorize_user_access(
        self, requester: Optional[UserAuthorization], target_user_id: str, action: str = "read"
    ) -> None:
        """Enforce role & user isolation security rules."""
        if not isinstance(target_user_id, str) or not target_user_id.strip():
            raise ValueError("target_user_id must be a non-empty string")
        clean_target = target_user_id.strip()

        # Authorize against security boundary first
        allowed, reason = self._security.authorize(
            user=requester,
            resource="notifications",
            action=action,
        )
        if not allowed:
            raise PermissionError(reason)

        assert requester is not None

        # User Isolation rule: user can only access their own notifications unless Admin
        if not requester.is_admin and requester.user_id != clean_target:
            self._security.audit_logger.log(
                user_id=requester.user_id,
                event_type="UNAUTHORIZED_CROSS_USER_NOTIFICATION_ACCESS",
                resource=f"notifications:{clean_target}",
                action=action,
                outcome="DENY",
                details=f"User '{requester.user_id}' attempted cross-user notification access to target user '{clean_target}'",
            )
            raise PermissionError(
                f"Access denied: user '{requester.user_id}' is not authorized to access notifications of user '{clean_target}'"
            )

    def sanitize_metadata(
        self, requester: Optional[UserAuthorization], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Sanitize secrets and filter protected proprietary research/parameters from metadata."""
        if not isinstance(metadata, dict):
            return {}
        return self._security.filter_protected_payload(requester, metadata)

    def get_notifications(
        self,
        requester: Optional[UserAuthorization],
        target_user_id: str,
        category: Optional[Union[NotificationCategory, str]] = None,
        unread_only: bool = False,
        include_archived: bool = False,
    ) -> List[Notification]:
        """Retrieve notifications for a user, filtered by category, read status, or archive status."""
        self._authorize_user_access(requester, target_user_id, action="get_notifications")

        all_notifs = self._repo.get_notifications(target_user_id.strip())

        clean_cat = None
        if category is not None:
            if isinstance(category, NotificationCategory):
                clean_cat = category
            elif isinstance(category, str) and category.strip():
                try:
                    clean_cat = NotificationCategory(category.strip().lower())
                except ValueError:
                    pass

        filtered = []
        for n in all_notifs:
            if not include_archived and n.is_archived:
                continue
            if unread_only and n.is_read:
                continue
            if clean_cat is not None and n.category != clean_cat:
                continue

            # Sanitize metadata before returning
            sanitized_meta = self.sanitize_metadata(requester, n.metadata)
            if sanitized_meta != n.metadata:
                n = Notification(
                    notification_id=n.notification_id,
                    user_id=n.user_id,
                    category=n.category,
                    severity=n.severity,
                    title=n.title,
                    message=n.message,
                    timestamp=n.timestamp,
                    is_read=n.is_read,
                    is_archived=n.is_archived,
                    metadata=sanitized_meta,
                )
            filtered.append(n)

        return filtered

    def get_unread_count(
        self, requester: Optional[UserAuthorization], target_user_id: str
    ) -> int:
        """Get total count of unread non-archived notifications for user."""
        notifs = self.get_notifications(
            requester=requester,
            target_user_id=target_user_id,
            unread_only=True,
            include_archived=False,
        )
        return len(notifs)

    def create_notification(
        self,
        requester: Optional[UserAuthorization],
        target_user_id: str,
        category: Union[NotificationCategory, str],
        severity: Union[NotificationSeverity, str],
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
    ) -> Notification:
        """Create a new notification for target user."""
        self._authorize_user_access(requester, target_user_id, action="create_notification")

        ts = float(timestamp) if timestamp is not None else time.time()
        meta = metadata or {}
        sanitized_meta = self.sanitize_metadata(requester, meta)

        notif = Notification(
            notification_id=f"notif_{uuid.uuid4().hex[:10]}",
            user_id=target_user_id.strip(),
            category=category,
            severity=severity,
            title=SecretSanitizer.sanitize_string(title),
            message=SecretSanitizer.sanitize_string(message),
            timestamp=ts,
            is_read=False,
            is_archived=False,
            metadata=sanitized_meta,
        )
        return self._repo.save(notif)

    def mark_as_read(
        self, requester: Optional[UserAuthorization], target_user_id: str, notification_id: str
    ) -> Notification:
        """Mark a specific notification as read."""
        self._authorize_user_access(requester, target_user_id, action="mark_as_read")

        notif = self._repo.get_by_id(target_user_id.strip(), notification_id.strip())
        if notif is None:
            raise KeyError(f"Notification '{notification_id}' not found for user '{target_user_id}'")

        updated = notif.with_read(True)
        return self._repo.save(updated)

    def mark_all_as_read(
        self, requester: Optional[UserAuthorization], target_user_id: str
    ) -> int:
        """Mark all unread notifications for user as read."""
        self._authorize_user_access(requester, target_user_id, action="mark_all_as_read")

        all_notifs = self._repo.get_notifications(target_user_id.strip())
        marked_count = 0
        for n in all_notifs:
            if not n.is_read:
                updated = n.with_read(True)
                self._repo.save(updated)
                marked_count += 1
        return marked_count

    def archive_notification(
        self, requester: Optional[UserAuthorization], target_user_id: str, notification_id: str
    ) -> Notification:
        """Archive a specific notification."""
        self._authorize_user_access(requester, target_user_id, action="archive_notification")

        notif = self._repo.get_by_id(target_user_id.strip(), notification_id.strip())
        if notif is None:
            raise KeyError(f"Notification '{notification_id}' not found for user '{target_user_id}'")

        updated = notif.with_archived(True)
        return self._repo.save(updated)

    def delete_notification(
        self, requester: Optional[UserAuthorization], target_user_id: str, notification_id: str
    ) -> bool:
        """Delete a notification by ID."""
        self._authorize_user_access(requester, target_user_id, action="delete_notification")

        return self._repo.delete(target_user_id.strip(), notification_id.strip())

    def create_notification_from_event(
        self,
        event: NotificationEvent,
        fallback_target_user_id: Optional[str] = None,
        workspace_service: Optional[Any] = None,
    ) -> Optional[Notification]:
        """Ingest a real system event and persist as user notification if target user specified and user preferences allow."""
        if not isinstance(event, NotificationEvent):
            raise ValueError("event must be a NotificationEvent instance")

        target_uid = event.target_user_id or fallback_target_user_id
        if not target_uid:
            return None

        clean_uid = target_uid.strip()

        ws_svc = workspace_service or self._workspace_service
        # Check Workspace Notification Preferences if workspace_service is available
        if ws_svc is not None:
            try:
                ws = ws_svc._repo.get_workspace(clean_uid) if hasattr(ws_svc, "_repo") else None
                if ws and hasattr(ws, "notification_preferences"):
                    prefs = ws.notification_preferences
                    if not prefs.in_app_enabled:
                        return None
                    if not prefs.is_category_enabled(event.category):
                        return None
                    if not prefs.is_severity_allowed(event.severity):
                        return None
            except Exception:
                pass  # Fallback to saving if preference check fails

        # Sanitize event title, message, and payload
        sanitized_payload = SecretSanitizer.sanitize_data(event.payload)
        if not isinstance(sanitized_payload, dict):
            sanitized_payload = {}

        notif = Notification(
            notification_id=f"notif_evt_{event.event_id}",
            user_id=clean_uid,
            category=event.category,
            severity=event.severity,
            title=SecretSanitizer.sanitize_string(event.title),
            message=SecretSanitizer.sanitize_string(event.message),
            timestamp=event.timestamp,
            is_read=False,
            is_archived=False,
            metadata={
                "event_id": event.event_id,
                "event_type": event.event_type,
                "payload": sanitized_payload,
                "version": event.version,
                "source": event.source,
                "correlation_id": event.correlation_id,
                "status": event.status,
            },
        )
        return self._repo.save(notif)

    def map_real_host_events(
        self,
        requester: Optional[UserAuthorization],
        target_user_id: str,
        project1_connected: bool,
        signal_action: Optional[str],
        signal_symbol: Optional[str],
        provider_status: Optional[str],
        provider_name: Optional[str],
        timestamp: Optional[float] = None,
    ) -> List[Notification]:
        """Generate honest notifications from real host state components (Project 1, Market Provider, Workspace)."""
        self._authorize_user_access(requester, target_user_id, action="map_events")

        ts = float(timestamp) if timestamp is not None else time.time()
        created: List[Notification] = []

        # 1. Project 1 Engine / Signal Event
        if project1_connected:
            if signal_action and signal_action.upper() in ("BUY", "SELL"):
                sym = signal_symbol or "XAUUSD"
                evt = NotificationEvent(
                    event_id=f"p1_sig_{int(ts)}",
                    event_type="SIGNAL_EMITTED",
                    category=NotificationCategory.SIGNAL,
                    severity=NotificationSeverity.INFO,
                    title=f"Project 1 Signal Emitted ({signal_action.upper()})",
                    message=f"Validated {signal_action.upper()} signal emitted for {sym} via Project1IntegrationPort.",
                    timestamp=ts,
                    target_user_id=target_user_id,
                    payload={"action": signal_action, "symbol": sym},
                )
                n = self.create_notification_from_event(evt)
                if n:
                    created.append(n)
        else:
            evt = NotificationEvent(
                event_id=f"p1_disc_{int(ts)}",
                event_type="PROJECT1_DISCONNECTED",
                category=NotificationCategory.SYSTEM,
                severity=NotificationSeverity.WARNING,
                title="Project 1 Disconnected",
                message="Project 1 trading engine is disconnected. Displaying honest unavailable state.",
                timestamp=ts,
                target_user_id=target_user_id,
            )
            n = self.create_notification_from_event(evt)
            if n:
                created.append(n)

        # 2. Market Data Provider Health Event
        if provider_status == "connected" and provider_name:
            evt = NotificationEvent(
                event_id=f"prov_ready_{int(ts)}",
                event_type="PROVIDER_HEALTHY",
                category=NotificationCategory.MARKET_HEALTH,
                severity=NotificationSeverity.SUCCESS,
                title=f"Market Provider Active ({provider_name})",
                message=f"Connected to {provider_name} market data feed.",
                timestamp=ts,
                target_user_id=target_user_id,
                payload={"provider": provider_name},
            )
            n = self.create_notification_from_event(evt)
            if n:
                created.append(n)
        elif provider_status == "disconnected":
            evt = NotificationEvent(
                event_id=f"prov_disc_{int(ts)}",
                event_type="PROVIDER_DISCONNECTED",
                category=NotificationCategory.MARKET_HEALTH,
                severity=NotificationSeverity.WARNING,
                title="Market Data Provider Disconnected",
                message="No live market data provider attached. Connect provider to stream candles.",
                timestamp=ts,
                target_user_id=target_user_id,
            )
            n = self.create_notification_from_event(evt)
            if n:
                created.append(n)

        return created

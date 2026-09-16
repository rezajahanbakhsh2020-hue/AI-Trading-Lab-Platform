"""Notification delivery application service.

Coordinates authorization checks, strict user isolation, secret sanitization,
user policy evaluation, and outbound dispatch of NotificationEvent and MarketAlert objects.
"""

from typing import Any, Dict, Optional
import time

from src.platform.domain.alert import MarketAlert
from src.platform.domain.notification import NotificationEvent
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.integrations.notification_delivery import (
    NotificationDeliveryAttempt,
    NotificationDeliveryPort,
)
from src.platform.services.security import SecretSanitizer, SecurityBoundaryService
from src.platform.services.user_authorization import UserAuthorizationService

REASON_UNREGISTERED_USER = "user is not registered or authorized"
REASON_DELIVERY_DISABLED = "notification delivery is disabled for user"
REASON_SECURITY_DENIED = "security boundary denied notification delivery"
REASON_USER_ISOLATION_DENIED = "user is not authorized to deliver notifications for target user"


class NotificationDeliveryService:
    """Application service for authorized notification and alert delivery."""

    def __init__(
        self,
        delivery_port: NotificationDeliveryPort,
        user_auth_service: Optional[UserAuthorizationService] = None,
        security_service: Optional[SecurityBoundaryService] = None,
    ) -> None:
        if delivery_port is None or not isinstance(delivery_port, NotificationDeliveryPort):
            raise ValueError("delivery_port must be a NotificationDeliveryPort instance")
        self._port = delivery_port
        self._auth_service = user_auth_service
        self._security = security_service or SecurityBoundaryService()

    def _evaluate_delivery_permission(
        self,
        requester: Optional[UserAuthorization],
        target_user_id: str,
    ) -> tuple[Optional[UserAuthorization], Optional[NotificationDeliveryAttempt]]:
        clean_target = target_user_id.strip()

        # 1. Enforce strict User Isolation: caller cannot deliver to another user's target_user_id unless Admin
        if requester is not None:
            if not requester.is_admin and requester.user_id != clean_target:
                self._security.audit_logger.log(
                    user_id=requester.user_id,
                    event_type="UNAUTHORIZED_CROSS_USER_NOTIFICATION_DELIVERY",
                    resource=f"notifications:{clean_target}",
                    action="deliver",
                    outcome="DENY",
                    details=f"User '{requester.user_id}' attempted cross-user notification delivery to '{clean_target}'",
                )
                raise PermissionError(
                    f"Access denied: user '{requester.user_id}' is not authorized to deliver notifications for user '{clean_target}'"
                )

        # 2. Retrieve user authorization configuration
        target_user: Optional[UserAuthorization] = None
        if self._auth_service is not None:
            target_user = self._auth_service.get_authorized_user(clean_target)

        if target_user is None and requester is not None and requester.user_id == clean_target:
            target_user = requester

        if target_user is not None:
            if not target_user.delivery_enabled:
                return target_user, NotificationDeliveryAttempt(
                    success=False,
                    user_id=clean_target,
                    reason=REASON_DELIVERY_DISABLED,
                    channel="in_process",
                    externally_delivered=False,
                    detail=f"User '{clean_target}' has delivery_enabled=False",
                )
        elif self._auth_service is not None:
            return None, NotificationDeliveryAttempt(
                success=False,
                user_id=clean_target,
                reason=REASON_UNREGISTERED_USER,
                channel="in_process",
                externally_delivered=False,
                detail=f"User '{clean_target}' is not registered in UserAuthorizationService",
            )

        # 3. Check SecurityBoundaryService authorization
        allowed, sec_reason = self._security.authorize(
            user=target_user or requester,
            resource="notifications",
            action="deliver",
        )
        if not allowed:
            return target_user, NotificationDeliveryAttempt(
                success=False,
                user_id=clean_target,
                reason=REASON_SECURITY_DENIED,
                channel="in_process",
                externally_delivered=False,
                detail=sec_reason,
            )

        return target_user, None

    def deliver_event_to_user(
        self,
        target_user_id: str,
        event: NotificationEvent,
        channel: Optional[str] = None,
        requester: Optional[UserAuthorization] = None,
    ) -> NotificationDeliveryAttempt:
        """Deliver a NotificationEvent to a target user after strict authorization & sanitization."""
        if not isinstance(target_user_id, str) or not target_user_id.strip():
            raise ValueError("target_user_id must be a non-empty string")
        clean_uid = target_user_id.strip()

        if not isinstance(event, NotificationEvent):
            raise ValueError("event must be a NotificationEvent instance")

        user_auth, denied_attempt = self._evaluate_delivery_permission(requester, clean_uid)
        if denied_attempt is not None:
            return denied_attempt

        # Secret Sanitization before delivery
        sanitized_payload = SecretSanitizer.sanitize_data(event.payload)
        if not isinstance(sanitized_payload, dict):
            sanitized_payload = {}

        sanitized_event = NotificationEvent(
            event_id=event.event_id,
            event_type=event.event_type,
            category=event.category,
            severity=event.severity,
            title=SecretSanitizer.sanitize_string(event.title),
            message=SecretSanitizer.sanitize_string(event.message),
            timestamp=event.timestamp,
            target_user_id=clean_uid,
            payload=sanitized_payload,
        )

        return self._port.deliver_event(
            user_id=clean_uid,
            event=sanitized_event,
            channel=channel,
        )

    def deliver_alert_to_user(
        self,
        target_user_id: str,
        alert: MarketAlert,
        channel: Optional[str] = None,
        requester: Optional[UserAuthorization] = None,
    ) -> NotificationDeliveryAttempt:
        """Deliver a MarketAlert to a target user after strict authorization & sanitization."""
        if not isinstance(target_user_id, str) or not target_user_id.strip():
            raise ValueError("target_user_id must be a non-empty string")
        clean_uid = target_user_id.strip()

        if not isinstance(alert, MarketAlert):
            raise ValueError("alert must be a MarketAlert instance")

        user_auth, denied_attempt = self._evaluate_delivery_permission(requester, clean_uid)
        if denied_attempt is not None:
            return denied_attempt

        # Secret Sanitization before delivery
        sanitized_details = SecretSanitizer.sanitize_data(alert.details) if alert.details else None
        if sanitized_details is not None and not isinstance(sanitized_details, dict):
            sanitized_details = None

        sanitized_alert = MarketAlert(
            id=alert.id,
            kind=alert.kind,
            severity=alert.severity,
            status=alert.status,
            message=SecretSanitizer.sanitize_string(alert.message),
            symbol=alert.symbol,
            timeframe=alert.timeframe,
            created_at=alert.created_at,
            details=sanitized_details,
        )

        return self._port.deliver_alert(
            user_id=clean_uid,
            alert=sanitized_alert,
            channel=channel,
        )

    def deliver_alert(
        self,
        user_id: str,
        alert: MarketAlert,
        channel: Optional[str] = None,
        requester: Optional[UserAuthorization] = None,
    ) -> NotificationDeliveryAttempt:
        """Stable contract method compatible with NotificationDeliveryPort."""
        return self.deliver_alert_to_user(
            target_user_id=user_id,
            alert=alert,
            channel=channel,
            requester=requester,
        )

    def describe(self) -> Dict[str, Any]:
        """Describe notification delivery service status."""
        return {
            "name": "NotificationDeliveryService",
            "port": self._port.describe(),
            "has_auth_service": self._auth_service is not None,
        }

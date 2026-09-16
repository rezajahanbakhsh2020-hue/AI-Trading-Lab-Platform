"""Notification delivery application service.

Coordinates authorization checks, secret sanitization, user policy evaluation,
and outbound dispatch of MarketAlert objects via NotificationDeliveryPort.
"""

from typing import Any, Dict, Optional, Tuple
import uuid

from src.platform.domain.alert import MarketAlert
from src.platform.domain.notification_delivery import (
    NOTIFICATION_DELIVERY_DELIVERED,
    NOTIFICATION_DELIVERY_DENIED,
    NOTIFICATION_DELIVERY_FAILED,
    NotificationDelivery,
)
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.integrations.notification_delivery import (
    NotificationDeliveryAttempt,
    NotificationDeliveryPort,
)
from src.platform.services.security import SecretSanitizer, SecurityBoundaryService
from src.platform.services.user_authorization import UserAuthorizationService

REASON_UNREGISTERED_USER = "user is not registered or authorized"
REASON_DELIVERY_DISABLED = "notification delivery is disabled for user"
REASON_SECURITY_DENIED = "security boundary denied alert delivery"
REASON_CHANNEL_FAILED = "delivery channel failed"


class NotificationDeliveryService:
    """Application service for authorized notification alert delivery."""

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

    def deliver_alert_to_user(
        self,
        user_id: str,
        alert: MarketAlert,
        channel: Optional[str] = None,
        requester: Optional[UserAuthorization] = None,
    ) -> NotificationDelivery:
        """Deliver a MarketAlert to a target user after strict authorization & sanitization."""
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id must be a non-empty string")
        clean_uid = user_id.strip()

        if not isinstance(alert, MarketAlert):
            raise ValueError("alert must be a MarketAlert instance")

        delivery_id = f"notif_del_{uuid.uuid4().hex[:10]}"

        # 1. Look up user authorization & delivery_enabled flag
        user_auth: Optional[UserAuthorization] = None
        if self._auth_service is not None:
            user_auth = self._auth_service.get_authorized_user(clean_uid)

        if user_auth is None and requester is not None and requester.user_id == clean_uid:
            user_auth = requester

        if user_auth is not None:
            if not user_auth.delivery_enabled:
                return NotificationDelivery(
                    delivery_id=delivery_id,
                    user_id=clean_uid,
                    status=NOTIFICATION_DELIVERY_DENIED,
                    reason=REASON_DELIVERY_DISABLED,
                    alert=alert,
                    channel=channel or "in_memory",
                    detail=f"User {clean_uid} has delivery_enabled=False",
                )
        elif self._auth_service is not None:
            # Service requires registered user
            return NotificationDelivery(
                delivery_id=delivery_id,
                user_id=clean_uid,
                status=NOTIFICATION_DELIVERY_DENIED,
                reason=REASON_UNREGISTERED_USER,
                alert=alert,
                channel=channel or "in_memory",
                detail=f"User {clean_uid} is not registered in UserAuthorizationService",
            )

        # 2. Check SecurityBoundaryService permission
        allowed, sec_reason = self._security.authorize(
            user=user_auth or requester,
            resource="alerts",
            action="deliver",
        )
        if not allowed:
            return NotificationDelivery(
                delivery_id=delivery_id,
                user_id=clean_uid,
                status=NOTIFICATION_DELIVERY_DENIED,
                reason=REASON_SECURITY_DENIED,
                alert=alert,
                channel=channel or "in_memory",
                detail=sec_reason,
            )

        # 3. Sanitize MarketAlert message and details before outbound dispatch
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

        # 4. Dispatch via outbound port
        attempt: NotificationDeliveryAttempt = self._port.deliver_alert(
            user_id=clean_uid,
            alert=sanitized_alert,
            channel=channel,
        )

        if not attempt.success:
            return NotificationDelivery(
                delivery_id=delivery_id,
                user_id=clean_uid,
                status=NOTIFICATION_DELIVERY_FAILED,
                reason=REASON_CHANNEL_FAILED,
                alert=sanitized_alert,
                channel=attempt.channel,
                detail=attempt.reason,
                timestamp=attempt.timestamp,
            )

        return NotificationDelivery(
            delivery_id=delivery_id,
            user_id=clean_uid,
            status=NOTIFICATION_DELIVERY_DELIVERED,
            reason=attempt.reason,
            alert=sanitized_alert,
            channel=attempt.channel,
            detail=attempt.detail,
            timestamp=attempt.timestamp,
        )

    def describe(self) -> Dict[str, Any]:
        """Describe notification delivery service status."""
        return {
            "name": "NotificationDeliveryService",
            "port": self._port.describe(),
            "has_auth_service": self._auth_service is not None,
        }

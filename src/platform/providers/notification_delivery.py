"""In-process notification delivery adapter.

Records outbound notification/alert delivery attempts for testing and development
with honest in-process semantics (channel='in_process'). Does NOT falsely claim external
delivery. Optionally forwards to NotificationService for in-app inbox persistence.
"""

from typing import Any, Dict, List, Optional
import time

from src.platform.domain.alert import MarketAlert
from src.platform.domain.notification import (
    NotificationCategory,
    NotificationEvent,
    NotificationSeverity,
)
from src.platform.integrations.notification_delivery import (
    NotificationDeliveryAttempt,
    NotificationDeliveryPort,
)
from src.platform.services.notification import NotificationService


def _map_alert_severity(severity: str) -> NotificationSeverity:
    sev = severity.lower()
    if sev == "critical":
        return NotificationSeverity.ERROR
    elif sev == "warning":
        return NotificationSeverity.WARNING
    return NotificationSeverity.INFO


def _map_alert_category(kind: str) -> NotificationCategory:
    k = kind.lower()
    if k == "signal":
        return NotificationCategory.SIGNAL
    elif k in ("freshness", "provider", "price"):
        return NotificationCategory.MARKET_HEALTH
    elif k == "security":
        return NotificationCategory.SYSTEM
    return NotificationCategory.SYSTEM


class RecordingNotificationDeliveryAdapter(NotificationDeliveryPort):
    """Records delivery attempts in-process with honest semantics without contacting third-party services."""

    def __init__(
        self,
        available: bool = True,
        notification_service: Optional[NotificationService] = None,
    ) -> None:
        self.available = available
        self.notification_service = notification_service
        self.attempts: List[Dict[str, Any]] = []
        self._disabled_channels: set[str] = set()

    def set_channel_enabled(self, channel: str, enabled: bool) -> None:
        """Enable or disable a specific delivery channel dynamically."""
        ch = channel.strip().lower()
        if enabled:
            self._disabled_channels.discard(ch)
        else:
            self._disabled_channels.add(ch)

    def deliver_event(
        self,
        user_id: str,
        event: NotificationEvent,
        channel: Optional[str] = None,
    ) -> NotificationDeliveryAttempt:
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id must be a non-empty string")
        if not isinstance(event, NotificationEvent):
            raise ValueError("event must be a NotificationEvent instance")

        ch = (channel or "in_process").strip().lower()
        ts = time.time()

        if not self.available or ch in self._disabled_channels:
            attempt = NotificationDeliveryAttempt(
                success=False,
                user_id=user_id.strip(),
                reason=f"delivery channel '{ch}' is unavailable",
                channel=ch,
                detail=f"in-process delivery attempt failed on channel '{ch}'",
                timestamp=ts,
            )
            self.attempts.append({
                "type": "event",
                "attempt": attempt.to_dict(),
                "event": event,
            })
            return attempt

        # Honest in-process recorded attempt
        attempt = NotificationDeliveryAttempt(
            success=True,
            user_id=user_id.strip(),
            reason=f"event '{event.event_id}' recorded in-process via channel '{ch}'",
            channel=ch,
            detail=f"recorded in-process attempt {len(self.attempts) + 1}",
            timestamp=ts,
        )
        self.attempts.append({
            "type": "event",
            "attempt": attempt.to_dict(),
            "event": event,
        })

        if self.notification_service is not None:
            self.notification_service.create_notification_from_event(
                event=event,
                fallback_target_user_id=user_id.strip(),
            )

        return attempt

    def deliver_alert(
        self,
        user_id: str,
        alert: MarketAlert,
        channel: Optional[str] = None,
    ) -> NotificationDeliveryAttempt:
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id must be a non-empty string")
        if not isinstance(alert, MarketAlert):
            raise ValueError("alert must be a MarketAlert instance")

        ch = (channel or "in_process").strip().lower()
        ts = time.time()

        if not self.available or ch in self._disabled_channels:
            attempt = NotificationDeliveryAttempt(
                success=False,
                user_id=user_id.strip(),
                reason=f"delivery channel '{ch}' is unavailable",
                channel=ch,
                detail=f"in-process alert delivery attempt failed on channel '{ch}'",
                timestamp=ts,
            )
            self.attempts.append({
                "type": "alert",
                "attempt": attempt.to_dict(),
                "alert": alert.to_dict(),
            })
            return attempt

        attempt = NotificationDeliveryAttempt(
            success=True,
            user_id=user_id.strip(),
            reason=f"alert '{alert.id}' recorded in-process via channel '{ch}'",
            channel=ch,
            detail=f"recorded in-process attempt {len(self.attempts) + 1}",
            timestamp=ts,
        )
        self.attempts.append({
            "type": "alert",
            "attempt": attempt.to_dict(),
            "alert": alert.to_dict(),
        })

        if self.notification_service is not None:
            cat = _map_alert_category(alert.kind)
            sev = _map_alert_severity(alert.severity)
            meta = dict(alert.details) if alert.details else {}
            meta["alert_id"] = alert.id
            meta["timeframe"] = alert.timeframe

            evt = NotificationEvent(
                event_id=f"alert_evt_{alert.id}_{int(ts)}",
                event_type="ALERT_TRIGGERED",
                category=cat,
                severity=sev,
                title=f"Alert: {alert.symbol} ({alert.kind.upper()})",
                message=alert.message,
                timestamp=ts,
                target_user_id=user_id.strip(),
                payload=meta,
            )
            self.notification_service.create_notification_from_event(evt)

        return attempt

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "RecordingNotificationDeliveryAdapter",
            "available": self.available,
            "recorded_count": len(self.attempts),
            "disabled_channels": sorted(list(self._disabled_channels)),
            "notification_service_attached": self.notification_service is not None,
        }

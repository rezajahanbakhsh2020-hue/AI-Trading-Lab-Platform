"""In-memory notification delivery adapter.

Records outbound alert delivery attempts for testing and development. Can also
optionally forward alerts to NotificationService for in-app inbox delivery.
"""

from typing import Any, Dict, List, Optional
import time

from src.platform.domain.alert import MarketAlert
from src.platform.domain.notification import NotificationCategory, NotificationSeverity
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
    elif k in ("freshness", "provider"):
        return NotificationCategory.MARKET_HEALTH
    elif k == "security":
        return NotificationCategory.SYSTEM
    return NotificationCategory.SYSTEM


class RecordingNotificationDeliveryAdapter(NotificationDeliveryPort):
    """Records alert delivery attempts without contacting external third-party services."""

    def __init__(
        self,
        available: bool = True,
        notification_service: Optional[NotificationService] = None,
    ) -> None:
        self.available = available
        self.notification_service = notification_service
        self.delivered: List[Dict[str, Any]] = []
        self._disabled_channels: set[str] = set()

    def set_channel_enabled(self, channel: str, enabled: bool) -> None:
        """Enable or disable a specific delivery channel dynamically."""
        ch = channel.strip().lower()
        if enabled:
            self._disabled_channels.discard(ch)
        else:
            self._disabled_channels.add(ch)

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

        ch = (channel or "in_memory").strip().lower()
        ts = time.time()

        if not self.available or ch in self._disabled_channels:
            attempt = NotificationDeliveryAttempt(
                success=False,
                user_id=user_id.strip(),
                reason=f"delivery channel '{ch}' is unavailable",
                channel=ch,
                detail=f"attempt failed on channel {ch}",
                timestamp=ts,
            )
            self.delivered.append({
                "attempt": attempt.to_dict(),
                "alert": alert.to_dict(),
            })
            return attempt

        # Success path
        attempt = NotificationDeliveryAttempt(
            success=True,
            user_id=user_id.strip(),
            reason=f"alert '{alert.id}' delivered via {ch}",
            channel=ch,
            detail=f"recorded attempt {len(self.delivered) + 1}",
            timestamp=ts,
        )
        self.delivered.append({
            "attempt": attempt.to_dict(),
            "alert": alert.to_dict(),
        })

        # Forward to NotificationService if attached
        if self.notification_service is not None:
            cat = _map_alert_category(alert.kind)
            sev = _map_alert_severity(alert.severity)
            meta = dict(alert.details) if alert.details else {}
            meta["alert_id"] = alert.id
            meta["timeframe"] = alert.timeframe

            # Create system notification event or direct notification for target user
            from src.platform.domain.notification import NotificationEvent
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
            "recorded_count": len(self.delivered),
            "disabled_channels": sorted(list(self._disabled_channels)),
            "notification_service_attached": self.notification_service is not None,
        }

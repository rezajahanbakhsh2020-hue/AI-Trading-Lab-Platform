"""Notification delivery domain model.

Immutable operational result of delivering a MarketAlert or notification event
to an authorized target user via outbound notification channels.
"""

from dataclasses import dataclass
import time
from typing import Any, Dict, Optional

from src.platform.domain.alert import MarketAlert

NOTIFICATION_DELIVERY_DELIVERED = "DELIVERED"
NOTIFICATION_DELIVERY_FAILED = "FAILED"
NOTIFICATION_DELIVERY_DENIED = "DENIED"

VALID_NOTIFICATION_DELIVERY_STATUSES = (
    NOTIFICATION_DELIVERY_DELIVERED,
    NOTIFICATION_DELIVERY_FAILED,
    NOTIFICATION_DELIVERY_DENIED,
)


@dataclass(frozen=True)
class NotificationDelivery:
    """Immutable operational outcome of a notification delivery attempt to a target user."""

    delivery_id: str
    user_id: str
    status: str
    reason: str
    alert: MarketAlert
    channel: str = "in_memory"
    detail: Optional[str] = None
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.delivery_id, str) or not self.delivery_id.strip():
            raise ValueError("delivery_id must be a non-empty string")
        object.__setattr__(self, "delivery_id", self.delivery_id.strip())

        if not isinstance(self.user_id, str) or not self.user_id.strip():
            raise ValueError("user_id must be a non-empty string")
        object.__setattr__(self, "user_id", self.user_id.strip())

        status_upper = self.status.upper() if isinstance(self.status, str) else ""
        if status_upper not in VALID_NOTIFICATION_DELIVERY_STATUSES:
            raise ValueError(
                f"status must be one of {VALID_NOTIFICATION_DELIVERY_STATUSES}, got {self.status!r}"
            )
        object.__setattr__(self, "status", status_upper)

        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")
        object.__setattr__(self, "reason", self.reason.strip())

        if not isinstance(self.alert, MarketAlert):
            raise ValueError("alert must be a MarketAlert instance")

        if not isinstance(self.channel, str) or not self.channel.strip():
            raise ValueError("channel must be a non-empty string")
        object.__setattr__(self, "channel", self.channel.strip().lower())

        if self.detail is not None:
            if not isinstance(self.detail, str) or not self.detail.strip():
                raise ValueError("detail must be a non-empty string if provided")
            object.__setattr__(self, "detail", self.detail.strip())

        if isinstance(self.timestamp, bool) or not isinstance(self.timestamp, (int, float)):
            raise ValueError("timestamp must be a non-negative real number")
        ts = float(self.timestamp) if self.timestamp > 0 else time.time()
        object.__setattr__(self, "timestamp", ts)

    @property
    def delivered(self) -> bool:
        return self.status == NOTIFICATION_DELIVERY_DELIVERED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delivery_id": self.delivery_id,
            "user_id": self.user_id,
            "status": self.status,
            "delivered": self.delivered,
            "reason": self.reason,
            "alert": self.alert.to_dict(),
            "channel": self.channel,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }

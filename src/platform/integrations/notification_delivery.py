"""Notification delivery integration port.

Outbound Ports-and-Adapters boundary for delivering NotificationEvent and MarketAlert
notifications to targeted users. Concrete delivery transport adapters live behind this port.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import time
from typing import Any, Dict, Optional

from src.platform.domain.alert import MarketAlert
from src.platform.domain.notification import NotificationEvent


@dataclass(frozen=True)
class NotificationDeliveryAttempt:
    """Immutable infrastructure result of one outbound delivery attempt."""

    success: bool
    user_id: str
    reason: str
    channel: str = "in_process"
    status_code: str = "DELIVERED"  # e.g. IN_APP_AVAILABLE, EXTERNAL_NOT_CONFIGURED, EXTERNAL_CONFIGURED, DELIVERY_FAILED, DELIVERY_UNAVAILABLE
    externally_delivered: bool = False
    detail: Optional[str] = None
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("success must be a boolean")

        if not isinstance(self.user_id, str) or not self.user_id.strip():
            raise ValueError("user_id must be a non-empty string")
        object.__setattr__(self, "user_id", self.user_id.strip())

        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")
        object.__setattr__(self, "reason", self.reason.strip())

        if not isinstance(self.channel, str) or not self.channel.strip():
            raise ValueError("channel must be a non-empty string")
        object.__setattr__(self, "channel", self.channel.strip().lower())

        if not isinstance(self.status_code, str) or not self.status_code.strip():
            raise ValueError("status_code must be a non-empty string")
        object.__setattr__(self, "status_code", self.status_code.strip().upper())

        if not isinstance(self.externally_delivered, bool):
            raise ValueError("externally_delivered must be a boolean")

        if self.detail is not None:
            if not isinstance(self.detail, str) or not self.detail.strip():
                raise ValueError("detail must be a non-empty string if provided")
            object.__setattr__(self, "detail", self.detail.strip())

        if isinstance(self.timestamp, bool) or not isinstance(self.timestamp, (int, float)):
            raise ValueError("timestamp must be a non-negative real number")
        ts = float(self.timestamp) if self.timestamp > 0 else time.time()
        object.__setattr__(self, "timestamp", ts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "user_id": self.user_id,
            "reason": self.reason,
            "channel": self.channel,
            "status_code": self.status_code,
            "externally_delivered": self.externally_delivered,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }


class NotificationDeliveryPort(ABC):
    """Abstract outbound port for delivering events/alerts to targeted users."""

    @abstractmethod
    def deliver_event(
        self,
        user_id: str,
        event: NotificationEvent,
        channel: Optional[str] = None,
    ) -> NotificationDeliveryAttempt:
        """Deliver the given NotificationEvent to target user_id."""
        raise NotImplementedError

    @abstractmethod
    def deliver_alert(
        self,
        user_id: str,
        alert: MarketAlert,
        channel: Optional[str] = None,
    ) -> NotificationDeliveryAttempt:
        """Deliver the given MarketAlert to target user_id."""
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> Dict[str, Any]:
        """Return an I/O-free description of the notification delivery channel."""
        raise NotImplementedError

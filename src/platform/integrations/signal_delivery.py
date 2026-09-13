"""Signal delivery integration port.

Outbound Ports-and-Adapters boundary for delivering a generated Signal to
an authorized consumer. Channel-specific infrastructure (Telegram, email,
webhooks) lives behind this port and must not leak into the application layer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.platform.domain.signal import Signal


@dataclass(frozen=True)
class SignalDeliveryAttempt:
    """Immutable infrastructure result of one outbound delivery attempt."""

    success: bool
    consumer_id: str
    reason: str
    channel: Optional[str] = None
    detail: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("success must be a boolean")
        if not isinstance(self.consumer_id, str) or not self.consumer_id.strip():
            raise ValueError("consumer_id must be a non-empty string")
        object.__setattr__(self, "consumer_id", self.consumer_id.strip())
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")
        object.__setattr__(self, "reason", self.reason.strip())
        if self.channel is not None:
            if not isinstance(self.channel, str) or not self.channel.strip():
                raise ValueError("channel must be a non-empty string if provided")
            object.__setattr__(self, "channel", self.channel.strip())
        if self.detail is not None:
            if not isinstance(self.detail, str) or not self.detail.strip():
                raise ValueError("detail must be a non-empty string if provided")
            object.__setattr__(self, "detail", self.detail.strip())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "consumer_id": self.consumer_id,
            "reason": self.reason,
            "channel": self.channel,
            "detail": self.detail,
        }


class SignalDeliveryPort(ABC):
    """Abstract outbound port for delivering generated signals."""

    @abstractmethod
    def deliver(
        self,
        consumer_id: str,
        signal: Signal,
        symbol: str,
    ) -> SignalDeliveryAttempt:
        """Deliver the given signal to consumer_id for symbol."""
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> Dict[str, Any]:
        """Return an I/O-free description of the delivery channel."""
        raise NotImplementedError

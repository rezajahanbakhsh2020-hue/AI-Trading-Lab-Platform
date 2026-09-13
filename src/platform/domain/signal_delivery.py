"""Signal delivery domain model.

Immutable operational result of attempting to deliver a generated Signal
to an authorized consumer. Distinct from Telegram-specific delivery and
from signal generation itself.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .signal import Signal

DELIVERY_STATUS_DELIVERED = "DELIVERED"
DELIVERY_STATUS_NOT_DELIVERED = "NOT_DELIVERED"

VALID_DELIVERY_STATUSES = (
    DELIVERY_STATUS_DELIVERED,
    DELIVERY_STATUS_NOT_DELIVERED,
)


@dataclass(frozen=True)
class SignalDelivery:
    """Immutable outcome of a signal delivery attempt."""

    status: str
    reason: str
    consumer_id: str
    symbol: str
    signal: Signal
    channel: Optional[str] = None
    detail: Optional[str] = None

    def __post_init__(self) -> None:
        status_upper = self.status.upper() if isinstance(self.status, str) else ""
        if status_upper not in VALID_DELIVERY_STATUSES:
            raise ValueError(
                f"status must be one of {VALID_DELIVERY_STATUSES}, got {self.status!r}"
            )
        object.__setattr__(self, "status", status_upper)

        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")
        object.__setattr__(self, "reason", self.reason.strip())

        if not isinstance(self.consumer_id, str) or not self.consumer_id.strip():
            raise ValueError("consumer_id must be a non-empty string")
        object.__setattr__(self, "consumer_id", self.consumer_id.strip())

        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        object.__setattr__(self, "symbol", self.symbol.strip())

        if not isinstance(self.signal, Signal):
            raise ValueError("signal must be a Signal instance")

        if self.channel is not None:
            if not isinstance(self.channel, str) or not self.channel.strip():
                raise ValueError("channel must be a non-empty string if provided")
            object.__setattr__(self, "channel", self.channel.strip())

        if self.detail is not None:
            if not isinstance(self.detail, str) or not self.detail.strip():
                raise ValueError("detail must be a non-empty string if provided")
            object.__setattr__(self, "detail", self.detail.strip())

    @property
    def delivered(self) -> bool:
        return self.status == DELIVERY_STATUS_DELIVERED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "delivered": self.delivered,
            "reason": self.reason,
            "consumer_id": self.consumer_id,
            "symbol": self.symbol,
            "signal": self.signal.to_dict(),
            "channel": self.channel,
            "detail": self.detail,
        }

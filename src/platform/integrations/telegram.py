"""Telegram delivery integration port (Part 19: Telegram Delivery Boundary).

Outbound integration port for sending presented signals to authorized Telegram destinations.
Follows Hexagonal Ports-and-Adapters principles, keeping application logic independent
from concrete Telegram API libraries.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.platform.domain.presented_signal import PresentedSignal


@dataclass(frozen=True)
class TelegramDeliveryResult:
    """Immutable result of a Telegram message delivery attempt."""

    success: bool
    chat_id: str
    message_id: Optional[str] = None
    reason: Optional[str] = None
    failure_code: Optional[str] = None  # e.g., UNCONFIGURED_CREDENTIALS, INVALID_CHAT_ID, RATE_LIMITED, UNAUTHORIZED_USER, NETWORK_ERROR
    is_retryable: bool = False
    correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "chat_id": self.chat_id,
            "message_id": self.message_id,
            "reason": self.reason,
            "failure_code": self.failure_code,
            "is_retryable": self.is_retryable,
            "correlation_id": self.correlation_id,
        }


class TelegramDeliveryPort(ABC):
    """Abstract outbound port for delivering signals via Telegram."""

    @abstractmethod
    def send_signal(self, chat_id: str, signal: PresentedSignal) -> TelegramDeliveryResult:
        """Send formatted signal message to chat_id."""
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> Dict[str, Any]:
        """Return description of Telegram delivery port status."""
        raise NotImplementedError

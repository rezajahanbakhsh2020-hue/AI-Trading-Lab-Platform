"""Transactional email delivery integration port.

Outbound Ports-and-Adapters boundary for sending transactional emails (recovery, security, system notifications).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import time
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class EmailDeliveryResult:
    """Immutable result of an outbound email delivery attempt."""

    success: bool
    recipient_email: str
    status_code: str  # e.g. SENT, NOT_CONFIGURED, DELIVERY_FAILED, DISABLED, INVALID_RECIPIENT
    reason: str
    message_id: Optional[str] = None
    externally_delivered: bool = False
    detail: Optional[str] = None
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("success must be a boolean")

        if not isinstance(self.recipient_email, str) or not self.recipient_email.strip():
            raise ValueError("recipient_email must be a non-empty string")
        object.__setattr__(self, "recipient_email", self.recipient_email.strip().lower())

        if not isinstance(self.status_code, str) or not self.status_code.strip():
            raise ValueError("status_code must be a non-empty string")
        object.__setattr__(self, "status_code", self.status_code.strip().upper())

        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")
        object.__setattr__(self, "reason", self.reason.strip())

        if self.message_id is not None:
            if not isinstance(self.message_id, str) or not self.message_id.strip():
                raise ValueError("message_id must be a non-empty string if provided")
            object.__setattr__(self, "message_id", self.message_id.strip())

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
            "recipient_email": self.recipient_email,
            "status_code": self.status_code,
            "reason": self.reason,
            "message_id": self.message_id,
            "externally_delivered": self.externally_delivered,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }


class EmailDeliveryPort(ABC):
    """Abstract outbound port for delivering transactional emails."""

    @abstractmethod
    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        sender_email: Optional[str] = None,
    ) -> EmailDeliveryResult:
        """Send a transactional email to recipient."""
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> Dict[str, Any]:
        """Return an I/O-free description of the email delivery provider and channel status."""
        raise NotImplementedError

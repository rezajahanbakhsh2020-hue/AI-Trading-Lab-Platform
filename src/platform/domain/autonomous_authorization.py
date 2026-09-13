"""Autonomous authorization domain model (Part 15: Full Autonomous Authorization).

Immutable result object describing the outcome of evaluating a trade setup,
trade signal, provider selection, and trade readiness for autonomous execution authorization.
"""

from dataclasses import dataclass
import numbers
from typing import Any, Dict, Optional

from src.platform.domain.provider_selection import ProviderSelection
from src.platform.domain.trade_readiness import TradeReadiness
from src.platform.domain.trade_signal import TradeSignal

AUTHORIZATION_STATUS_AUTHORIZED = "AUTHORIZED"
AUTHORIZATION_STATUS_REJECTED = "REJECTED"

VALID_AUTHORIZATION_STATUSES = (
    AUTHORIZATION_STATUS_AUTHORIZED,
    AUTHORIZATION_STATUS_REJECTED,
)


@dataclass(frozen=True)
class AutonomousAuthorization:
    """Immutable outcome of full autonomous authorization evaluation."""

    status: str
    reason: str
    timestamp: float
    trade_signal: TradeSignal
    provider_selection: Optional[ProviderSelection] = None
    trade_readiness: Optional[TradeReadiness] = None
    detail: Optional[str] = None

    def __post_init__(self) -> None:
        status_upper = self.status.upper() if isinstance(self.status, str) else ""
        if status_upper not in VALID_AUTHORIZATION_STATUSES:
            raise ValueError(
                f"status must be one of {VALID_AUTHORIZATION_STATUSES}, got {self.status!r}"
            )
        object.__setattr__(self, "status", status_upper)

        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")
        object.__setattr__(self, "reason", self.reason.strip())

        if isinstance(self.timestamp, bool) or not isinstance(self.timestamp, numbers.Real):
            raise ValueError("timestamp must be a numeric real value")
        ts_float = float(self.timestamp)
        if ts_float < 0:
            raise ValueError("timestamp must be non-negative")
        object.__setattr__(self, "timestamp", ts_float)

        if not isinstance(self.trade_signal, TradeSignal):
            raise ValueError("trade_signal must be a TradeSignal instance")

        if self.provider_selection is not None and not isinstance(
            self.provider_selection, ProviderSelection
        ):
            raise ValueError("provider_selection must be a ProviderSelection instance if provided")

        if self.trade_readiness is not None and not isinstance(
            self.trade_readiness, TradeReadiness
        ):
            raise ValueError("trade_readiness must be a TradeReadiness instance if provided")

        if self.detail is not None:
            if not isinstance(self.detail, str) or not self.detail.strip():
                raise ValueError("detail must be a non-empty string if provided")
            object.__setattr__(self, "detail", self.detail.strip())

    @property
    def is_authorized(self) -> bool:
        """Return True if status is AUTHORIZED."""
        return self.status == AUTHORIZATION_STATUS_AUTHORIZED

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation of AutonomousAuthorization."""
        return {
            "status": self.status,
            "is_authorized": self.is_authorized,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "trade_signal": self.trade_signal.to_dict(),
            "provider_selection": (
                self.provider_selection.to_dict()
                if self.provider_selection is not None
                else None
            ),
            "trade_readiness": (
                self.trade_readiness.to_dict()
                if self.trade_readiness is not None
                else None
            ),
            "detail": self.detail,
        }

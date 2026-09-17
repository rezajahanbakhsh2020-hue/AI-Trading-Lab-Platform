"""Trading workflow domain model (Part 16: Cross-Domain Trading Flow).

Immutable result object describing the outcome of executing a cross-domain
trading workflow that connects market data, provider selection, strategy signals,
trade readiness, and autonomous authorization.
"""

from dataclasses import dataclass
import numbers
from typing import Any, Dict, Optional

from src.platform.domain.autonomous_authorization import AutonomousAuthorization
from src.platform.domain.order_intent import OrderIntent
from src.platform.domain.provider_selection import ProviderSelection
from src.platform.domain.trade_readiness import TradeReadiness
from src.platform.domain.trade_signal import TradeSignal

WORKFLOW_STATUS_EXECUTED = "EXECUTED"
WORKFLOW_STATUS_DENIED = "DENIED"
WORKFLOW_STATUS_NOT_READY = "NOT_READY"

VALID_WORKFLOW_STATUSES = (
    WORKFLOW_STATUS_EXECUTED,
    WORKFLOW_STATUS_DENIED,
    WORKFLOW_STATUS_NOT_READY,
)


@dataclass(frozen=True)
class TradingWorkflowResult:
    """Immutable result of a cross-domain trading workflow execution."""

    symbol: str
    timeframe: str
    status: str
    reason: str
    timestamp: float
    authorization: AutonomousAuthorization
    trade_signal: TradeSignal
    provider_selection: Optional[ProviderSelection] = None
    trade_readiness: Optional[TradeReadiness] = None
    order_intent: Optional[OrderIntent] = None
    detail: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        object.__setattr__(self, "symbol", self.symbol.strip())

        if not isinstance(self.timeframe, str) or not self.timeframe.strip():
            raise ValueError("timeframe must be a non-empty string")
        object.__setattr__(self, "timeframe", self.timeframe.strip())

        status_upper = self.status.upper() if isinstance(self.status, str) else ""
        if status_upper not in VALID_WORKFLOW_STATUSES:
            raise ValueError(
                f"status must be one of {VALID_WORKFLOW_STATUSES}, got {self.status!r}"
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

        if not isinstance(self.authorization, AutonomousAuthorization):
            raise ValueError("authorization must be an AutonomousAuthorization instance")

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

        if self.order_intent is not None and not isinstance(
            self.order_intent, OrderIntent
        ):
            raise ValueError("order_intent must be an OrderIntent instance if provided")

        if self.detail is not None:
            if not isinstance(self.detail, str) or not self.detail.strip():
                raise ValueError("detail must be a non-empty string if provided")
            object.__setattr__(self, "detail", self.detail.strip())

    @property
    def is_executed(self) -> bool:
        """Return True if workflow status is EXECUTED."""
        return self.status == WORKFLOW_STATUS_EXECUTED

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation of TradingWorkflowResult."""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "status": self.status,
            "is_executed": self.is_executed,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "authorization": self.authorization.to_dict(),
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
            "order_intent": (
                self.order_intent.to_dict()
                if self.order_intent is not None
                else None
            ),
            "detail": self.detail,
        }

"""Validated strategy state domain model (Part 18: Strategy Validation Flow).

Immutable result object describing the outcome of evaluating a strategy's
backtest performance and stability against platform validation rules.
"""

from dataclasses import dataclass
import numbers
from typing import Any, Dict, Optional

from src.platform.domain.backtest import BacktestResult
from src.platform.domain.readiness import Readiness
from src.platform.domain.stability import Stability
from src.platform.domain.strategy_result import StrategyResult
from src.platform.domain.trade_setup import TradeSetup

STRATEGY_STATUS_VALIDATED = "VALIDATED"
STRATEGY_STATUS_REJECTED = "REJECTED"
STRATEGY_STATUS_UNVALIDATED = "UNVALIDATED"

VALID_STRATEGY_STATUSES = (
    STRATEGY_STATUS_VALIDATED,
    STRATEGY_STATUS_REJECTED,
    STRATEGY_STATUS_UNVALIDATED,
)


@dataclass(frozen=True)
class ValidatedStrategyState:
    """Immutable validated strategy state domain object."""

    strategy_name: str
    status: str
    reason: str
    timestamp: float
    backtest_result: Optional[BacktestResult] = None
    stability: Optional[Stability] = None
    trade_setup: Optional[TradeSetup] = None
    detail: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.strategy_name, str) or not self.strategy_name.strip():
            raise ValueError("strategy_name must be a non-empty string")
        object.__setattr__(self, "strategy_name", self.strategy_name.strip())

        status_upper = self.status.upper() if isinstance(self.status, str) else ""
        if status_upper not in VALID_STRATEGY_STATUSES:
            raise ValueError(
                f"status must be one of {VALID_STRATEGY_STATUSES}, got {self.status!r}"
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

        if self.backtest_result is not None and not isinstance(
            self.backtest_result, BacktestResult
        ):
            raise ValueError("backtest_result must be a BacktestResult instance if provided")

        if self.stability is not None and not isinstance(self.stability, Stability):
            raise ValueError("stability must be a Stability instance if provided")

        if self.trade_setup is not None and not isinstance(self.trade_setup, TradeSetup):
            raise ValueError("trade_setup must be a TradeSetup instance if provided")

        if self.detail is not None:
            if not isinstance(self.detail, str) or not self.detail.strip():
                raise ValueError("detail must be a non-empty string if provided")
            object.__setattr__(self, "detail", self.detail.strip())

    @property
    def is_validated(self) -> bool:
        """Return True if strategy status is VALIDATED."""
        return self.status == STRATEGY_STATUS_VALIDATED

    def to_strategy_result(self, proposed_action: str = "no-signal") -> StrategyResult:
        """Convert validated strategy state into a StrategyResult for downstream signal pipeline."""
        stab = self.stability or Stability(score=0.0, risk_level="critical")
        readiness = Readiness(
            approved=self.is_validated,
            reason=self.reason,
            timestamp=self.timestamp,
        )
        return StrategyResult(
            strategy_name=self.strategy_name,
            timestamp=self.timestamp,
            proposed_action=proposed_action,
            stability=stab,
            readiness=readiness,
            trade_setup=self.trade_setup,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation of ValidatedStrategyState."""
        return {
            "strategy_name": self.strategy_name,
            "status": self.status,
            "is_validated": self.is_validated,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "backtest_result": (
                self.backtest_result.to_dict()
                if self.backtest_result is not None
                else None
            ),
            "stability": self.stability.to_dict() if self.stability is not None else None,
            "trade_setup": (
                self.trade_setup.to_dict()
                if self.trade_setup is not None
                else None
            ),
            "detail": self.detail,
        }

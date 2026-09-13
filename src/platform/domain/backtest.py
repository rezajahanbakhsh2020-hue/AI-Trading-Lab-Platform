"""Backtest result domain model (Part 17: Backtest Validation & Stability Flow).

Immutable result object describing the outcome of a backtest execution and
its mapping to platform stability and risk assessments.
"""

from dataclasses import dataclass
import numbers
from typing import Any, Dict, Optional

from src.platform.domain.stability import Stability


@dataclass(frozen=True)
class BacktestResult:
    """Immutable outcome of a strategy backtest execution."""

    strategy_name: str
    symbol: str
    timeframe: str
    total_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    net_profit: float
    stability: Optional[Stability] = None
    detail: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.strategy_name, str) or not self.strategy_name.strip():
            raise ValueError("strategy_name must be a non-empty string")
        object.__setattr__(self, "strategy_name", self.strategy_name.strip())

        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        object.__setattr__(self, "symbol", self.symbol.strip())

        if not isinstance(self.timeframe, str) or not self.timeframe.strip():
            raise ValueError("timeframe must be a non-empty string")
        object.__setattr__(self, "timeframe", self.timeframe.strip())

        if isinstance(self.total_trades, bool) or not isinstance(self.total_trades, int):
            raise ValueError("total_trades must be an integer")
        if self.total_trades < 0:
            raise ValueError("total_trades must be non-negative")

        for field_name in ("win_rate", "profit_factor", "max_drawdown", "net_profit"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, numbers.Real):
                raise ValueError(f"{field_name} must be a numeric real value")
            val_float = float(value)
            object.__setattr__(self, field_name, val_float)

        if not (0.0 <= self.win_rate <= 1.0):
            raise ValueError("win_rate must be between 0.0 and 1.0 inclusive")

        if self.profit_factor < 0:
            raise ValueError("profit_factor must be non-negative")

        if not (0.0 <= self.max_drawdown <= 1.0):
            raise ValueError("max_drawdown must be between 0.0 and 1.0 inclusive")

        if self.stability is not None and not isinstance(self.stability, Stability):
            raise ValueError("stability must be a Stability instance if provided")

        if self.detail is not None:
            if not isinstance(self.detail, str) or not self.detail.strip():
                raise ValueError("detail must be a non-empty string if provided")
            object.__setattr__(self, "detail", self.detail.strip())

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation of BacktestResult."""
        return {
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "net_profit": self.net_profit,
            "stability": self.stability.to_dict() if self.stability is not None else None,
            "detail": self.detail,
        }

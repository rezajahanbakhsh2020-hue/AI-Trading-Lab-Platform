"""Walk-Forward validation domain model.

Immutable domain objects describing walk-forward window results and aggregated
stability & risk validation outcomes.
"""

from dataclasses import dataclass
import numbers
from typing import Any, Dict, Optional, Sequence, Tuple

from src.platform.domain.stability import Stability


@dataclass(frozen=True)
class WalkForwardWindow:
    """Immutable representation of a single walk-forward window assessment."""

    window_index: int
    in_sample_trades: int
    in_sample_win_rate: float
    in_sample_profit_factor: float
    out_of_sample_trades: int
    out_of_sample_win_rate: float
    out_of_sample_profit_factor: float
    out_of_sample_max_drawdown: float
    out_of_sample_net_profit: float
    efficiency_ratio: float

    def __post_init__(self) -> None:
        if isinstance(self.window_index, bool) or not isinstance(self.window_index, int):
            raise ValueError("window_index must be an integer")
        if self.window_index < 0:
            raise ValueError("window_index must be non-negative")

        for field_name in ("in_sample_trades", "out_of_sample_trades"):
            val = getattr(self, field_name)
            if isinstance(val, bool) or not isinstance(val, int):
                raise ValueError(f"{field_name} must be an integer")
            if val < 0:
                raise ValueError(f"{field_name} must be non-negative")

        for field_name in (
            "in_sample_win_rate",
            "in_sample_profit_factor",
            "out_of_sample_win_rate",
            "out_of_sample_profit_factor",
            "out_of_sample_max_drawdown",
            "out_of_sample_net_profit",
            "efficiency_ratio",
        ):
            val = getattr(self, field_name)
            if isinstance(val, bool) or not isinstance(val, numbers.Real):
                raise ValueError(f"{field_name} must be a numeric real value")
            object.__setattr__(self, field_name, float(val))

        if not (0.0 <= self.in_sample_win_rate <= 1.0):
            raise ValueError("in_sample_win_rate must be between 0.0 and 1.0 inclusive")

        if self.in_sample_profit_factor < 0:
            raise ValueError("in_sample_profit_factor must be non-negative")

        if not (0.0 <= self.out_of_sample_win_rate <= 1.0):
            raise ValueError("out_of_sample_win_rate must be between 0.0 and 1.0 inclusive")

        if self.out_of_sample_profit_factor < 0:
            raise ValueError("out_of_sample_profit_factor must be non-negative")

        if not (0.0 <= self.out_of_sample_max_drawdown <= 1.0):
            raise ValueError("out_of_sample_max_drawdown must be between 0.0 and 1.0 inclusive")

        if self.efficiency_ratio < 0:
            raise ValueError("efficiency_ratio must be non-negative")

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation of WalkForwardWindow."""
        return {
            "window_index": self.window_index,
            "in_sample_trades": self.in_sample_trades,
            "in_sample_win_rate": self.in_sample_win_rate,
            "in_sample_profit_factor": self.in_sample_profit_factor,
            "out_of_sample_trades": self.out_of_sample_trades,
            "out_of_sample_win_rate": self.out_of_sample_win_rate,
            "out_of_sample_profit_factor": self.out_of_sample_profit_factor,
            "out_of_sample_max_drawdown": self.out_of_sample_max_drawdown,
            "out_of_sample_net_profit": self.out_of_sample_net_profit,
            "efficiency_ratio": self.efficiency_ratio,
        }


@dataclass(frozen=True)
class WalkForwardResult:
    """Immutable aggregate outcome of walk-forward stability and risk validation."""

    strategy_name: str
    symbol: str
    timeframe: str
    windows: Tuple[WalkForwardWindow, ...]
    overall_out_of_sample_win_rate: float
    overall_out_of_sample_profit_factor: float
    overall_out_of_sample_max_drawdown: float
    overall_out_of_sample_net_profit: float
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

        if not isinstance(self.windows, (list, tuple, Sequence)):
            raise ValueError("windows must be a sequence of WalkForwardWindow instances")
        windows_tuple = tuple(self.windows)
        for w in windows_tuple:
            if not isinstance(w, WalkForwardWindow):
                raise ValueError("all items in windows must be WalkForwardWindow instances")
        object.__setattr__(self, "windows", windows_tuple)

        for field_name in (
            "overall_out_of_sample_win_rate",
            "overall_out_of_sample_profit_factor",
            "overall_out_of_sample_max_drawdown",
            "overall_out_of_sample_net_profit",
        ):
            val = getattr(self, field_name)
            if isinstance(val, bool) or not isinstance(val, numbers.Real):
                raise ValueError(f"{field_name} must be a numeric real value")
            object.__setattr__(self, field_name, float(val))

        if not (0.0 <= self.overall_out_of_sample_win_rate <= 1.0):
            raise ValueError("overall_out_of_sample_win_rate must be between 0.0 and 1.0 inclusive")

        if self.overall_out_of_sample_profit_factor < 0:
            raise ValueError("overall_out_of_sample_profit_factor must be non-negative")

        if not (0.0 <= self.overall_out_of_sample_max_drawdown <= 1.0):
            raise ValueError("overall_out_of_sample_max_drawdown must be between 0.0 and 1.0 inclusive")

        if self.stability is not None and not isinstance(self.stability, Stability):
            raise ValueError("stability must be a Stability instance if provided")

        if self.detail is not None:
            if not isinstance(self.detail, str) or not self.detail.strip():
                raise ValueError("detail must be a non-empty string if provided")
            object.__setattr__(self, "detail", self.detail.strip())

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation of WalkForwardResult."""
        return {
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "windows": [w.to_dict() for w in self.windows],
            "overall_out_of_sample_win_rate": self.overall_out_of_sample_win_rate,
            "overall_out_of_sample_profit_factor": self.overall_out_of_sample_profit_factor,
            "overall_out_of_sample_max_drawdown": self.overall_out_of_sample_max_drawdown,
            "overall_out_of_sample_net_profit": self.overall_out_of_sample_net_profit,
            "stability": self.stability.to_dict() if self.stability is not None else None,
            "detail": self.detail,
        }

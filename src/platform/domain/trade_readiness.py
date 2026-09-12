"""Trade readiness domain model.

Immutable value object describing how far the current real market price is
from an existing structural trade setup (entry, stop loss,, and take-profit
levels``, together with an honest risk-distance assessment. It is built
only from real observed data quote prices and validated trade-setup levels``;
absent fields remain ``None`` and are never invented..
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional
import math
import numbers


@dataclass(frozen=True)
class TradeReadiness:
    """Immutable distance/risk assessment between a real quote price and a trade setup.



    Attribute semantics:
    - symbol/timeframe: identifiers of the assessed market context.
    - direction: the trade-setup direction ("buy" or "sell"), preserved from the
      validated trade setup..
    - entry_price/stop_loss/take_profit_*: preserved real setup levels..
    - current_price: the real observable price used as the entry-distance
      reference (best-effort side chosen honestly per direction:  ask for
      buy, bid for sell; ``None`` when the quote has no such side or no quote).
    - entry_distance_absolute / entry_distance_percent: distance between the
      real current price and the desired entry level; ``None`` when no
      comparable price is available..
    - stop_distance_absolute / stop_distance_percent: distance between the
      real current price and the stop-loss level, measured on the honest
      risk side per direction; ``None`` when no comparable price is available..
    - tp1_distance_percent / tp2_distance_percent / tp3_distance_percent:
      distance between the real current price and each take-profit level as a
      percentage of the current price;; ``None`` when no comparable price.
    - risk_reward_to_tp1: reward (entry→TP1) divided by risk (entry→SL),
      computed from the real setup levels alone; ``None`` when risk is zero.
    - levels_are_sane: bool derived only from real setup levels and the real
      current price: stops sit on the correct (opposite) side and every
      take-profit sits beyond the entry on the correct side;; ``False`` never
      implies fabricated data, it only reports the observed geometry..
    """

    symbol: str
    timeframe: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    current_price: Optional[float] = None
    entry_distance_absolute: Optional[float] = None
    entry_distance_percent: Optional[float] = None
    stop_distance_absolute: Optional[float] = None
    stop_distance_percent: Optional[float] = None
    tp1_distance_percent: Optional[float] = None
    tp2_distance_percent: Optional[float] = None
    tp3_distance_percent: Optional[float] = None
    risk_reward_to_tp1: Optional[float] = None
    levels_are_sane: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str):
            raise ValueError("symbol must be a string")
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty or whitespace")
        object.__setattr__(self, "symbol", self.symbol.strip())

        if not isinstance(self.timeframe, str):
            raise ValueError("timeframe must be a string")
        if not self.timeframe.strip():
            raise ValueError("timeframe must not be empty or whitespace")
        object.__setattr__(self, "timeframe", self.timeframe.strip())

        if not isinstance(self.direction, str):
            raise ValueError("direction must be a string")
        direction_normalized = self.direction.strip().lower()
        if direction_normalized not in ("buy", "sell"):
            raise ValueError("direction must be one of: buy, sell")
        object.__setattr__(self, "direction", direction_normalized)

        for field_name in (
            "entry_price",
            "stop_loss",
            "take_profit_1",
            "take_profit_2",
            "take_profit_3",
        ):
            value = getattr(self, field_name)
            if (
                not isinstance(value, numbers.Real)
                or isinstance(value, bool)
            ):
                raise ValueError(f"{field_name} must be a numeric real value")
            value_float = float(value)
            if not math.isfinite(value_float) or value_float <= 0:
                raise ValueError(f"{field_name} must be finite and greater than zero")
            object.__setattr__(self, field_name, value_float)

        for field_name in (
            "current_price",
            "entry_distance_absolute",
            "entry_distance_percent",
            "stop_distance_absolute",
            "stop_distance_percent",
            "tp1_distance_percent",
            "tp2_distance_percent",
            "tp3_distance_percent",
            "risk_reward_to_tp1",
        ):
            value = getattr(self, field_name)
            if value is None:
                continue
            if not isinstance(value, numbers.Real) or isinstance(value, bool):
                raise ValueError(f"{field_name} must be a numeric real value if provided")
            value_float = float(value)
            if not math.isfinite(value_float):
                raise ValueError(f"{field_name} must be finite")
            object.__setattr__(self, field_name, value_float)

        if not isinstance(self.levels_are_sane, bool):
            raise ValueError("levels_are_sane must be a bool")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "take_profit_3": self.take_profit_3,
            "current_price": self.current_price,
            "entry_distance_absolute": self.entry_distance_absolute,
            "entry_distance_percent": self.entry_distance_percent,
            "stop_distance_absolute": self.stop_distance_absolute,
            "stop_distance_percent": self.stop_distance_percent,
            "tp1_distance_percent": self.tp1_distance_percent,
            "tp2_distance_percent": self.tp2_distance_percent,
            "tp3_distance_percent": self.tp3_distance_percent,
            "risk_reward_to_tp1": self.risk_reward_to_tp1,
            "levels_are_sane": self.levels_are_sane,
        }


def current_price_side(direction: str) -> str:
    """Return the honest quote side used as current price for a direction.



    For a long (buy) entry the market is crossed at the ask; for a short
    (sell) entry at the bid. This honors the existing Quote semantics where
    bid/ask are the real observable two-sided prices..
    """
    if direction == "buy":
        return "ask"
    return "bid"
"""Trade setup domain model.

Immutable value object defining structural entry, stop loss, and take profit
parameters for BUY and SELL trades.
"""

from dataclasses import dataclass
from typing import Union, Dict, Any
import numbers
import math

VALID_DIRECTIONS = ("buy", "sell")


class FloatCallable(float):
    """Float subclass that is callable without arguments to return float(self).

    Ensures seamless compatibility whether risk_reward_ratio is accessed as an
    attribute or invoked as a zero-argument method.
    """

    def __call__(self) -> float:
        return float(self)


@dataclass(frozen=True)
class TradeSetup:
    """Immutable trade setup value object."""

    symbol: str
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    timestamp: Union[int, float, str]
    direction: str

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str):
            raise ValueError("symbol must be a string")
        if not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        object.__setattr__(self, "symbol", self.symbol.strip())

        if not isinstance(self.direction, str):
            raise ValueError("direction must be a string")
        direction_normalized = self.direction.strip().lower()
        if direction_normalized not in VALID_DIRECTIONS:
            raise ValueError(
                f"direction must be one of: {', '.join(VALID_DIRECTIONS)}; "
                f"got {self.direction!r}"
            )
        object.__setattr__(self, "direction", direction_normalized)

        if not isinstance(self.timestamp, (int, float, str)):
            raise ValueError("timestamp must be an int, float, or ISO-formatted string")
        if isinstance(self.timestamp, str) and not self.timestamp.strip():
            raise ValueError("timestamp string must not be empty or whitespace")
        if isinstance(self.timestamp, (int, float)):
            if not math.isfinite(self.timestamp):
                raise ValueError("numeric timestamp must be finite")

        price_fields = (
            "entry_price",
            "stop_loss",
            "take_profit_1",
            "take_profit_2",
            "take_profit_3",
        )

        for field_name in price_fields:
            value = getattr(self, field_name)

            if (
                not isinstance(value, numbers.Real)
                or isinstance(value, bool)
            ):
                raise ValueError(f"{field_name} must be a numeric real value")

            value_float = float(value)

            if not math.isfinite(value_float):
                raise ValueError(f"{field_name} must be finite")

            if value_float <= 0:
                raise ValueError(f"{field_name} must be greater than zero")

            object.__setattr__(self, field_name, value_float)

        entry = self.entry_price
        stop = self.stop_loss
        tp1 = self.take_profit_1
        tp2 = self.take_profit_2
        tp3 = self.take_profit_3

        if self.direction == "buy":
            if not (stop < entry < tp1 < tp2 < tp3):
                raise ValueError(
                    "for buy direction, prices must satisfy "
                    "stop_loss < entry_price < take_profit_1 "
                    "< take_profit_2 < take_profit_3"
                )

        elif self.direction == "sell":
            if not (stop > entry > tp1 >= tp2 >= tp3):
                raise ValueError(
                    "for sell direction, prices must satisfy "
                    "stop_loss > entry_price > take_profit_1 "
                    ">= take_profit_2 >= take_profit_3"
                )

    @property
    def risk(self) -> float:
        """Return absolute price risk per unit."""
        return abs(self.entry_price - self.stop_loss)

    @property
    def reward(self) -> float:
        """Return reward to TP1 per unit."""
        return abs(self.take_profit_1 - self.entry_price)

    @property
    def risk_reward_ratio(self) -> FloatCallable:
        """Return reward/risk ratio to TP1.

        The returned value behaves as a float and is also callable, allowing
        both ``setup.risk_reward_ratio`` and ``setup.risk_reward_ratio()``.
        """
        return FloatCallable(self.reward / self.risk)

    def get_risk_reward_ratio(self, tp_level: int = 1) -> float:
        """Return risk/reward ratio for the selected take-profit level."""
        if tp_level not in (1, 2, 3):
            raise ValueError("tp_level must be 1, 2, or 3")

        target = {
            1: self.take_profit_1,
            2: self.take_profit_2,
            3: self.take_profit_3,
        }[tp_level]

        reward = abs(target - self.entry_price)
        return reward / self.risk

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "take_profit_3": self.take_profit_3,
            "timestamp": self.timestamp,
            "direction": self.direction,
            "risk": self.risk,
            "reward": self.reward,
            "risk_reward_ratio": float(self.risk_reward_ratio),
        }

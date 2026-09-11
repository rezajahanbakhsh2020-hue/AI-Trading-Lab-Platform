"""Signal domain model.

Immutable value object representing an actionable trading signal generated
by a strategy or analysis module.
"""

from dataclasses import dataclass
from typing import Optional, Union, Dict, Any
import numbers
import math

VALID_ACTIONS = ("buy", "sell", "hold", "no-signal")


@dataclass(frozen=True)
class Signal:
    """Immutable value object representing a trading signal.

    Attributes:
        action: Signal action ("buy", "sell", "hold", "no-signal").
        strategy_name: Name of the strategy generating the signal (non-empty string).
        timestamp: Time of signal creation (int, float, or ISO string).
        confidence: Optional confidence score between 0.0 and 1.0 inclusive.
    """
    action: str
    strategy_name: str
    timestamp: Union[int, float, str]
    confidence: Optional[float] = None

    def __post_init__(self) -> None:
        if not isinstance(self.action, str):
            raise ValueError("action must be a string")
        action_normalized = self.action.strip().lower()
        if action_normalized == "no_signal":
            action_normalized = "no-signal"
        if action_normalized not in VALID_ACTIONS:
            raise ValueError(
                f"action must be one of: {', '.join(VALID_ACTIONS)}; got {self.action!r}"
            )
        object.__setattr__(self, "action", action_normalized)

        if not isinstance(self.strategy_name, str):
            raise ValueError("strategy_name must be a string")
        if not self.strategy_name.strip():
            raise ValueError("strategy_name must be a non-empty string")
        object.__setattr__(self, "strategy_name", self.strategy_name.strip())

        if not isinstance(self.timestamp, (int, float, str)):
            raise ValueError("timestamp must be an int, float, or ISO-formatted string")
        if isinstance(self.timestamp, str) and not self.timestamp.strip():
            raise ValueError("timestamp string must not be empty or whitespace")
        if isinstance(self.timestamp, (int, float)):
            if not math.isfinite(self.timestamp):
                raise ValueError("numeric timestamp must be finite")

        if self.confidence is not None:
            if not isinstance(self.confidence, numbers.Real) or isinstance(self.confidence, bool):
                raise ValueError("confidence must be a numeric real value if provided")
            if not math.isfinite(self.confidence):
                raise ValueError("confidence must be a finite number")
            conf_val = float(self.confidence)
            if not (0.0 <= conf_val <= 1.0):
                raise ValueError(
                    f"confidence must be between 0.0 and 1.0 inclusive; got {conf_val}"
                )
            object.__setattr__(self, "confidence", conf_val)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "strategy_name": self.strategy_name,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
        }

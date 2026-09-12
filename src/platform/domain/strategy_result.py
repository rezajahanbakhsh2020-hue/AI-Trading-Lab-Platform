"""Strategy evaluation result.

Immutable, already-evaluated strategy output that the platform may turn
into a trade signal. This object does not run strategies, fetch market
data, or invent prices. Callers supply previously validated domain
objects.
"""

from dataclasses import dataclass
from typing import Optional, Union, Dict, Any
import math

from .readiness import Readiness
from .signal import VALID_ACTIONS
from .stability import Stability
from .trade_setup import TradeSetup


@dataclass(frozen=True)
class StrategyResult:
    """Immutable strategy evaluation used as input to TradeSignalService."""

    strategy_name: str
    timestamp: Union[int, float, str]
    proposed_action: str
    stability: Stability
    readiness: Readiness
    trade_setup: Optional[TradeSetup] = None

    def __post_init__(self) -> None:
        if not isinstance(self.strategy_name, str):
            raise ValueError("strategy_name must be a string")
        name = self.strategy_name.strip()
        if name == "":
            raise ValueError("strategy_name must be a non-empty string")
        object.__setattr__(self, "strategy_name", name)

        if isinstance(self.timestamp, bool) or not isinstance(
            self.timestamp, (int, float, str)
        ):
            raise ValueError("timestamp must be an int, float, or ISO-formatted string")
        if isinstance(self.timestamp, str) and not self.timestamp.strip():
            raise ValueError("timestamp string must not be empty or whitespace")
        if isinstance(self.timestamp, (int, float)) and not math.isfinite(self.timestamp):
            raise ValueError("numeric timestamp must be finite")

        if not isinstance(self.proposed_action, str):
            raise ValueError("proposed_action must be a string")
        action = self.proposed_action.strip().lower()
        if action == "no_signal":
            action = "no-signal"
        if action not in VALID_ACTIONS:
            raise ValueError(
                "proposed_action must be one of: " + ", ".join(VALID_ACTIONS)
            )
        object.__setattr__(self, "proposed_action", action)

        if not isinstance(self.stability, Stability):
            raise ValueError("stability must be a Stability instance")
        if not isinstance(self.readiness, Readiness):
            raise ValueError("readiness must be a Readiness instance")
        if self.trade_setup is not None and not isinstance(self.trade_setup, TradeSetup):
            raise ValueError("trade_setup must be a TradeSetup instance if provided")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "timestamp": self.timestamp,
            "proposed_action": self.proposed_action,
            "stability": self.stability.to_dict(),
            "readiness": self.readiness.to_dict(),
            "trade_setup": None
            if self.trade_setup is None
            else self.trade_setup.to_dict(),
        }

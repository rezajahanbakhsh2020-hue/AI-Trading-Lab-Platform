"""Trade signal result.

Immutable application result produced from a StrategyResult. Wraps the
existing Signal domain object with readiness, stability, and optional
trade-setup context. Contains no I/O and invents no prices.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

from .readiness import Readiness
from .signal import Signal
from .stability import Stability
from .trade_setup import TradeSetup


@dataclass(frozen=True)
class TradeSignal:
    """Immutable trade-signal evaluation result."""

    signal: Signal
    readiness: Readiness
    stability: Stability
    reason: str
    tradable: bool
    trade_setup: Optional[TradeSetup] = None

    def __post_init__(self) -> None:
        if not isinstance(self.signal, Signal):
            raise ValueError("signal must be a Signal instance")
        if not isinstance(self.readiness, Readiness):
            raise ValueError("readiness must be a Readiness instance")
        if not isinstance(self.stability, Stability):
            raise ValueError("stability must be a Stability instance")
        if not isinstance(self.reason, str) or self.reason.strip() == "":
            raise ValueError("reason must be a non-empty string")
        object.__setattr__(self, "reason", self.reason.strip())
        if not isinstance(self.tradable, bool):
            raise ValueError("tradable must be a boolean")
        if self.trade_setup is not None and not isinstance(self.trade_setup, TradeSetup):
            raise ValueError("trade_setup must be a TradeSetup instance if provided")
        if self.tradable and self.signal.action not in ("buy", "sell"):
            raise ValueError("tradable signals must have action buy or sell")
        if not self.tradable and self.signal.action not in ("hold", "no-signal"):
            raise ValueError("non-tradable signals must have action hold or no-signal")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal": self.signal.to_dict(),
            "readiness": self.readiness.to_dict(),
            "stability": self.stability.to_dict(),
            "reason": self.reason,
            "tradable": self.tradable,
            "trade_setup": None
            if self.trade_setup is None
            else self.trade_setup.to_dict(),
        }

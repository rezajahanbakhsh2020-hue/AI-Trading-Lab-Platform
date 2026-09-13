"""Presented signal domain model (Part 19: Host Application & Signal Presentation).

Immutable domain object representing a trading signal produced by Project 1
and formatted for presentation/delivery in Project 2.

Rules:
- Strictly immutable (frozen dataclass).
- Preserves all real signal attributes from Project 1 without fabrication.
- Multiple take-profit levels are stored in a Tuple, preserving exact original order.
"""

from dataclasses import dataclass, field
import math
import numbers
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class PresentedSignal:
    """Immutable presented signal domain object for Project 2 presentation & delivery."""

    signal_id: str
    symbol: str
    signal_type: str
    timestamp: float
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profits: Tuple[float, ...] = field(default_factory=tuple)
    confidence: Optional[float] = None
    strategy_name: Optional[str] = None
    timeframe: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.signal_id, str) or not self.signal_id.strip():
            raise ValueError("signal_id must be a non-empty string")
        object.__setattr__(self, "signal_id", self.signal_id.strip())

        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        object.__setattr__(self, "symbol", self.symbol.strip())

        if not isinstance(self.signal_type, str) or not self.signal_type.strip():
            raise ValueError("signal_type must be a non-empty string")
        sig_type_clean = self.signal_type.strip().lower()
        if sig_type_clean not in ("buy", "sell", "hold", "no-signal"):
            raise ValueError("signal_type must be one of: buy, sell, hold, no-signal")
        object.__setattr__(self, "signal_type", sig_type_clean)

        if isinstance(self.timestamp, bool) or not isinstance(self.timestamp, numbers.Real):
            raise ValueError("timestamp must be a numeric real value")
        ts_float = float(self.timestamp)
        if ts_float < 0 or not math.isfinite(ts_float):
            raise ValueError("timestamp must be a non-negative finite number")
        object.__setattr__(self, "timestamp", ts_float)

        for field_name in ("entry_price", "stop_loss", "confidence"):
            val = getattr(self, field_name)
            if val is not None:
                if isinstance(val, bool) or not isinstance(val, numbers.Real):
                    raise ValueError(f"{field_name} must be a numeric real value if provided")
                val_float = float(val)
                if not math.isfinite(val_float):
                    raise ValueError(f"{field_name} must be finite")
                if field_name == "confidence" and not (0.0 <= val_float <= 1.0):
                    raise ValueError("confidence must be between 0.0 and 1.0 inclusive")
                object.__setattr__(self, field_name, val_float)

        if isinstance(self.take_profits, (list, tuple)):
            clean_tps = []
            for i, tp in enumerate(self.take_profits):
                if isinstance(tp, bool) or not isinstance(tp, numbers.Real):
                    raise ValueError(f"take_profit level at index {i} must be a numeric real value")
                tp_float = float(tp)
                if not math.isfinite(tp_float) or tp_float <= 0:
                    raise ValueError(f"take_profit level at index {i} must be positive finite number")
                clean_tps.append(tp_float)
            object.__setattr__(self, "take_profits", tuple(clean_tps))
        else:
            raise ValueError("take_profits must be a tuple or list")

        if self.strategy_name is not None:
            if not isinstance(self.strategy_name, str) or not self.strategy_name.strip():
                raise ValueError("strategy_name must be a non-empty string if provided")
            object.__setattr__(self, "strategy_name", self.strategy_name.strip())

        if self.timeframe is not None:
            if not isinstance(self.timeframe, str) or not self.timeframe.strip():
                raise ValueError("timeframe must be a non-empty string if provided")
            object.__setattr__(self, "timeframe", self.timeframe.strip())

        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation of PresentedSignal."""
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "signal_type": self.signal_type,
            "timestamp": self.timestamp,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profits": list(self.take_profits),
            "confidence": self.confidence,
            "strategy_name": self.strategy_name,
            "timeframe": self.timeframe,
            "metadata": dict(self.metadata),
        }

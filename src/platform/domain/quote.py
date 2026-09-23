"""Quote domain model.

Immutable value object representing a single-symbol market quote. Price fields
are stored only when supplied; missing values remain absent and are never
invented. Health/freshness is represented by an optional Availability object.
"""

from dataclasses import dataclass
from typing import Optional, Union, Dict, Any
import math
import numbers

from .availability import Availability


@dataclass(frozen=True)
class Quote:
    """Immutable market quote for one instrument."""

    symbol: str
    timestamp: Union[int, float, str]
    bid: Optional[float] = None
    ask: Optional[float] = None
    mid: Optional[float] = None
    last: Optional[float] = None
    change_percent: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    availability: Optional[Availability] = None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str):
            raise ValueError("symbol must be a string")
        symbol_normalized = self.symbol.strip()
        if symbol_normalized == "":
            raise ValueError("symbol must not be empty or whitespace")
        object.__setattr__(self, "symbol", symbol_normalized)

        if not isinstance(self.timestamp, (int, float, str)):
            raise ValueError("timestamp must be an int, float, or ISO-formatted string")
        if isinstance(self.timestamp, str) and not self.timestamp.strip():
            raise ValueError("timestamp string must not be empty or whitespace")
        if isinstance(self.timestamp, (int, float)):
            if isinstance(self.timestamp, bool) or not math.isfinite(self.timestamp):
                raise ValueError("numeric timestamp must be finite")

        price_fields = ("bid", "ask", "mid", "last", "high", "low")
        for name in price_fields:
            value = getattr(self, name)
            if value is None:
                continue
            if not isinstance(value, numbers.Real) or isinstance(value, bool):
                raise ValueError(f"{name} must be a numeric real value if provided")
            if not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
            object.__setattr__(self, name, float(value))

        # Derive mid price automatically from bid and ask when bid and ask are provided and mid is absent
        if self.mid is None and self.bid is not None and self.ask is not None:
            object.__setattr__(self, "mid", (self.bid + self.ask) / 2.0)

        if self.change_percent is not None:
            if not isinstance(self.change_percent, numbers.Real) or isinstance(self.change_percent, bool):
                raise ValueError("change_percent must be a numeric real value if provided")
            if not math.isfinite(self.change_percent):
                raise ValueError("change_percent must be a finite number")
            object.__setattr__(self, "change_percent", float(self.change_percent))

        if self.high is not None and self.low is not None and self.high < self.low:
            raise ValueError("high must be >= low")

        if self.availability is not None and not isinstance(self.availability, Availability):
            raise ValueError("availability must be an Availability instance if provided")

        has_price = any(getattr(self, name) is not None for name in ("bid", "ask", "mid", "last"))
        if not has_price:
            raise ValueError("quote must include at least one of bid, ask, mid, or last")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "bid": self.bid,
            "ask": self.ask,
            "mid": self.mid,
            "last": self.last,
            "change_percent": self.change_percent,
            "changePercent": self.change_percent,
            "high": self.high,
            "high24h": self.high,
            "low": self.low,
            "low24h": self.low,
            "availability": None if self.availability is None else self.availability.to_dict(),
        }

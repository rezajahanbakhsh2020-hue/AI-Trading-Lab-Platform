from dataclasses import dataclass
from typing import Optional, Union, Dict, Any
import numbers
import math


@dataclass(frozen=True)
class Candle:
    """Immutable value object representing a market candle.

    Timestamp: stored exactly as provided (int, float, or ISO-formatted string).
    OHLC: stored as floats and validated to be finite numbers.
    Volume: optional; if provided must be finite and non-negative.

    Note: The model validates relationships between OHLC values and raises
    ValueError on invalid input. The object is immutable after creation.
    """

    timestamp: Union[int, float, str]
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None

    def __post_init__(self) -> None:
        # Timestamp must be one of the accepted input types. We store it as
        # provided to avoid fabricating or altering the original value.
        if not isinstance(self.timestamp, (int, float, str)):
            raise ValueError("timestamp must be an int, float, or ISO-formatted string")

        # Validate OHLC are numeric real values and finite
        for name, val in (("open", self.open), ("high", self.high), ("low", self.low), ("close", self.close)):
            if not isinstance(val, numbers.Real):
                raise ValueError(f"{name} must be a numeric real value")
            if not math.isfinite(val):
                raise ValueError(f"{name} must be a finite number")

        # Convert OHLC to floats for consistent internal representation
        object.__setattr__(self, "open", float(self.open))
        object.__setattr__(self, "high", float(self.high))
        object.__setattr__(self, "low", float(self.low))
        object.__setattr__(self, "close", float(self.close))

        # Volume validation
        if self.volume is not None:
            if not isinstance(self.volume, numbers.Real):
                raise ValueError("volume must be numeric if provided")
            if not math.isfinite(self.volume) or self.volume < 0:
                raise ValueError("volume must be finite and non-negative")
            object.__setattr__(self, "volume", float(self.volume))

        # OHLC relationship checks
        if self.high < self.low:
            raise ValueError("high must be >= low")
        if self.high < self.open or self.high < self.close:
            raise ValueError("high must be >= open and close")
        if self.low > self.open or self.low > self.close:
            raise ValueError("low must be <= open and close")

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dict representation preserving stored values.

        The timestamp is returned exactly as provided at construction. If
        volume was not provided it remains None.
        """
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }

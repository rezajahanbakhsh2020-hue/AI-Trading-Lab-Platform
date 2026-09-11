"""Data freshness domain model.

Immutable value object describing how current a market-data snapshot is,
relative to a single reference instant. Missing timestamps are genuinely
unknown; ages are only computed when the timestamp is comparable with the
reference instant, and stale-ness is decided honestly from the real age --
never invented..
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, Union
import math
import numbers

VALID_FRESHNESS_STATUSES = (
    "fresh",
    "stale",
    "unknown",
    "unavailable",
)


@dataclass(frozen=True)
class DataFreshness:
    """Immutable freshness assessment for one market-data stream.



    Attribute semantics:
    - reference_timestamp: single instant all ages are measured against
      (float seconds since epoch when provided); may be ``None`` only when the
       reference was not supplied, in which case ages and relative status stay
       unknown (never fabricated)
    - candle/quote timestamps are preserved exactly as reported; the
       corresponding age_seconds fields are sind the measured age, or ``None``
       when the timestamp cannot be interpreted (unknown age, not zero).
    - ``status`` summarizes the overall freshness of the requested context
      using only the age(s) the caller actually supplied: "fresh"/"stale"
      when at least one age is known (the oldest age wins), "unknown" when
      no age is computable,, and "unavailable" when the snapshot explicitly
      reports there was no data for the context..
    """

    symbol: str
    timeframe: str
    status: str
    reference_timestamp: Optional[Union[int, float, str]] = None
    candle_timestamp: Optional[Union[int, float, str]] = None
    quote_timestamp: Optional[Union[int, float, str]] = None
    candle_age_seconds: Optional[float] = None
    quote_age_seconds: Optional[float] = None
    reason: Optional[str] = None

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

        if not isinstance(self.status, str):
            raise ValueError("status must be a string")
        status_normalized = self.status.strip().lower()
        if status_normalized not in VALID_FRESHNESS_STATUSES:

            raise ValueError(
                "status must be one of: " + ", ".join(VALID_FRESHNESS_STATUSES)
            )
        object.__setattr__(self, "status", status_normalized)

        if self.reference_timestamp is not None:
            _validate_timestamp(self.reference_timestamp, "reference_timestamp")
        if self.candle_timestamp is not None:

            _validate_timestamp(self.candle_timestamp, "candle_timestamp")
        if self.quote_timestamp is not None:
            _validate_timestamp(self.quote_timestamp, "quote_timestamp")

        for field_name in ("candle_age_seconds", "quote_age_seconds"):
            value = getattr(self, field_name)
            if value is None:
                continue
            if (
                not isinstance(value, numbers.Real)
                or isinstance(value, bool)
            ):
                raise ValueError(f"{field_name} must be a numeric real value if provided")
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{field_name} must be finite and non-negative")
            object.__setattr__(self, field_name, float(value))

        if self.reason is not None:
            if not isinstance(self.reason, str):
                raise ValueError("reason must be a string if provided")
            stripped = self.reason.strip()
            if stripped == "":
                raise ValueError("reason must not be empty or whitespace")
            object.__setattr__(self, "reason", stripped)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "status": self.status,
            "reference_timestamp": self.reference_timestamp,
            "candle_timestamp": self.candle_timestamp,
            "quote_timestamp": self.quote_timestamp,
            "candle_age_seconds": self.candle_age_seconds,
            "quote_age_seconds": self.quote_age_seconds,
            "reason": self.reason,
        }


def _validate_timestamp(value: Any, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{field_name} must be an int, float, or ISO-formatted string")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{field_name} string must not be empty or whitespace")
    if isinstance(value, (int, float)) and not math.isfinite(value):
        raise ValueError(f"{field_name} numeric timestamp must be finite")
"""Availability domain model.

Immutable value object describing whether market data is live, stale, closed,
offline, or unavailable. Presentation layers may map these statuses to UI
states; this model contains no presentation logic.
"""

from dataclasses import dataclass
from typing import Optional, Union, Dict, Any
import math
import numbers


VALID_STATUSES = (
    "live",
    "stale",
    "closed",
    "offline",
    "unavailable",
)


@dataclass(frozen=True)
class Availability:
    """Immutable health/freshness assessment for a market-data snapshot."""

    status: str
    timestamp: Optional[Union[int, float, str]] = None
    age_seconds: Optional[float] = None
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, str):
            raise ValueError("status must be a string")
        status_normalized = self.status.strip().lower()
        if status_normalized not in VALID_STATUSES:
            raise ValueError(
                "status must be one of: " + ", ".join(VALID_STATUSES)
            )
        object.__setattr__(self, "status", status_normalized)

        if self.timestamp is not None:
            if not isinstance(self.timestamp, (int, float, str)):
                raise ValueError("timestamp must be an int, float, or ISO-formatted string")
            if isinstance(self.timestamp, str) and not self.timestamp.strip():
                raise ValueError("timestamp string must not be empty or whitespace")
            if isinstance(self.timestamp, (int, float)):
                if isinstance(self.timestamp, bool) or not math.isfinite(self.timestamp):
                    raise ValueError("numeric timestamp must be finite")

        if self.age_seconds is not None:
            if not isinstance(self.age_seconds, numbers.Real) or isinstance(self.age_seconds, bool):
                raise ValueError("age_seconds must be a numeric real value if provided")
            if not math.isfinite(self.age_seconds) or self.age_seconds < 0:
                raise ValueError("age_seconds must be finite and non-negative")
            object.__setattr__(self, "age_seconds", float(self.age_seconds))

        if self.reason is not None:
            if not isinstance(self.reason, str):
                raise ValueError("reason must be a string if provided")
            stripped = self.reason.strip()
            if stripped == "":
                raise ValueError("reason must not be empty or whitespace")
            object.__setattr__(self, "reason", stripped)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "timestamp": self.timestamp,
            "age_seconds": self.age_seconds,
            "reason": self.reason,
        }

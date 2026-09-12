"""Readiness domain model.

Immutable assessment of whether a strategy evaluation is approved for
trade-signal emission. Presentation and execution layers may map this
to UI or order-routing states; this model contains no I/O.
"""

from dataclasses import dataclass
from typing import Optional, Union, Dict, Any
import math


@dataclass(frozen=True)
class Readiness:
    """Immutable trade-readiness verdict for a strategy result."""

    approved: bool
    reason: Optional[str] = None
    timestamp: Optional[Union[int, float, str]] = None

    def __post_init__(self) -> None:
        if not isinstance(self.approved, bool):
            raise ValueError("approved must be a boolean")

        if self.reason is not None:
            if not isinstance(self.reason, str):
                raise ValueError("reason must be a string if provided")
            stripped = self.reason.strip()
            if stripped == "":
                raise ValueError("reason must not be empty or whitespace")
            object.__setattr__(self, "reason", stripped)

        if self.timestamp is not None:
            if isinstance(self.timestamp, bool) or not isinstance(
                self.timestamp, (int, float, str)
            ):
                raise ValueError(
                    "timestamp must be an int, float, or ISO-formatted string"
                )
            if isinstance(self.timestamp, str) and not self.timestamp.strip():
                raise ValueError("timestamp string must not be empty or whitespace")
            if isinstance(self.timestamp, (int, float)) and not math.isfinite(
                self.timestamp
            ):
                raise ValueError("numeric timestamp must be finite")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }

"""Stability domain model.

Immutable value object representing strategy stability metrics, risk level,
and diagnostic indicators.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Dict, Any, Optional
import numbers
import math

VALID_RISK_LEVELS = (
    "low",
    "medium",
    "moderate",
    "high",
    "critical",
    "minimal",
)


class ImmutableDict(dict):
    """Read-only dict subclass that prevents in-place mutation."""

    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("metrics is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable

    def __ior__(self, other: Any) -> "ImmutableDict":
        raise TypeError("metrics is immutable")


@dataclass(frozen=True)
class Stability:
    """Immutable stability assessment for a strategy."""

    score: float
    risk_level: str
    metrics: Optional[Mapping[str, Any]] = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.score, numbers.Real)
            or isinstance(self.score, bool)
        ):
            raise ValueError("score must be a numeric real value")

        score_value = float(self.score)

        if not math.isfinite(score_value):
            raise ValueError("score must be finite")

        if not 0.0 <= score_value <= 1.0:
            raise ValueError("score must be between 0.0 and 1.0 inclusive")

        object.__setattr__(self, "score", score_value)

        if not isinstance(self.risk_level, str):
            raise ValueError("risk_level must be a string")

        risk_level_normalized = self.risk_level.strip().lower()

        if risk_level_normalized not in VALID_RISK_LEVELS:
            raise ValueError(
                "risk_level must be one of: "
                f"{', '.join(VALID_RISK_LEVELS)}"
            )

        object.__setattr__(
            self,
            "risk_level",
            risk_level_normalized,
        )

        if self.metrics is None:
            metrics_copy: Dict[str, Any] = {}
        elif not isinstance(self.metrics, Mapping):
            raise ValueError("metrics must be a mapping if provided")
        else:
            metrics_copy = dict(self.metrics)

        object.__setattr__(
            self,
            "metrics",
            ImmutableDict(metrics_copy),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "risk_level": self.risk_level,
            "metrics": dict(self.metrics),
        }

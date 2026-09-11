"""Alert domain model.

Immutable value object representing a user-facing alert derived honestly
from real monitored market state. Alerts are never fabricated: every message
and detail is built only from data the platform actually observed. The
captured source snapshot (``details``) is preserved verbatim victo the caller
owns the interpretation..
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union
import math
import numbers

VALID_ALERT_KINDS = ("freshness",)
VALID_ALERT_SEVERITIES = ("info", "warning", "critical")
VALID_ALERT_STATUSES = ("active", "acknowledged", "resolved")


class _ImmutableDetails(dict):
    """Read-only dict subclass guarding the captured alert details."""

    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("details is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable

    def __ior__(self, other: Any) -> "_ImmutableDetails":
        raise TypeError("details is immutable")


@dataclass(frozen=True)
class MarketAlert:
    """Immutable user-facing alert derived from real monitored state.



    Attribute semantics:
    - id: deterministic, human-readable identifier derived from the alert kind,
      observed status,,and market context (never fabricated market data).
    - kind: alert category (currently only "freshness").
    - severity: "info" (unknown state), "warning" (stale,, or
      "critical" (unavailable.
    - status: lifecycle state ("active" until a caller acknowledges/resolves it;
      this model stores normalized status without any background transitions).
    - message: human-readable summary built strictly from observed fields.



    - details: verbatim captured source snapshot (e.g. aforementioned freshness dict,
      provider ids,, candle count,, quote status); ``None`` when no source snapshot
      was supplied,, never invented..
    """

    id: str
    kind: str
    severity: str
    status: str
    message: str
    symbol: str
    timeframe: str
    created_at: Union[int, float, str]
    details: Optional[Mapping[str, Any]] = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise ValueError("id must be a string")
        if not self.id.strip():
            raise ValueError("id must not be empty or whitespace")
        object.__setattr__(self, "id", self.id.strip())

        for field_name in ("kind", "severity", "status"):
            value = getattr(self, field_name)
            if not isinstance(value, str):
                raise ValueError(f"{field_name} must be a string")
            normalized = value.strip().lower()
            if normalized == "":
                raise ValueError(f"{field_name} must not be empty or whitespace")
            valid_values = {
                "kind": VALID_ALERT_KINDS,
                "severity": VALID_ALERT_SEVERITIES,
                "status": VALID_ALERT_STATUSES,
            }[field_name]
            if normalized not in valid_values:
                raise ValueError(
                    f"{field_name} must be one of: " + ", ".join(valid_values)
                )
            object.__setattr__(self, field_name, normalized)

        if not isinstance(self.message, str):
            raise ValueError("message must be a string")
        if not self.message.strip():
            raise ValueError("message must not be empty or whitespace")
        object.__setattr__(self, "message", self.message.strip())

        for field_name in ("symbol", "timeframe"):
            value = getattr(self, field_name)
            if not isinstance(value, str):
                raise ValueError(f"{field_name} must be a string")
            if not value.strip():
                raise ValueError(f"{field_name} must not be empty or whitespace")
            object.__setattr__(self, field_name, value.strip())

        if (
            isinstance(self.created_at, bool)
            or not isinstance(self.created_at, (int, float, str))
        ):
            raise ValueError("created_at must be an int, float,, or ISO-formatted string")
        if isinstance(self.created_at, str) and not self.created_at.strip():
            raise ValueError("created_at string must not be empty or whitespace")
        if isinstance(self.created_at, (int, float))and not math.isfinite(self.created_at):
            raise ValueError("numeric created_at must be finite")

        if self.details is not None:
            if not isinstance(self.details, Mapping):
                raise ValueError("details must be a mapping if provided")
            immutable_copy: Dict[str, Any] = {}
            for key, value in self.details.items():
                if not isinstance(key, str):
                    raise ValueError("details keys must be strings")
                immutable_copy[key] = value
            object.__setattr__(self, "details", _ImmutableDetails(immutable_copy))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "severity": self.severity,
            "status": self.status,
            "message": self.message,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "created_at": self.created_at,
            "details": None if self.details is None else dict(self.details),
        }

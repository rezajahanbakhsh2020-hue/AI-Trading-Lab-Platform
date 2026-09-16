"""Alert domain model.

Immutable value object representing a user-facing alert derived honestly
from real monitored market state. Alerts are never fabricated: every message
and detail is built only from data the platform actually observed. The
captured source snapshot (``details``) is preserved verbatim.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union
import math
import numbers

VALID_ALERT_KINDS = ("freshness", "price", "signal", "provider", "security")
VALID_ALERT_SEVERITIES = ("info", "warning", "critical")
VALID_ALERT_STATUSES = ("active", "acknowledged", "resolved")

VALID_CONDITION_TYPES = (
    "price_above",
    "price_below",
    "signal_action",
    "confidence_below",
    "provider_disconnect",
)


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
class AlertRule:
    """Immutable user-defined rule for generating alerts."""

    rule_id: str
    kind: str
    symbol: str
    condition_type: str
    threshold: Optional[float] = None
    expected_value: Optional[str] = None
    timeframe: str = "1h"
    enabled: bool = True
    created_at: Union[int, float, str] = 0

    def __post_init__(self) -> None:
        if not isinstance(self.rule_id, str) or not self.rule_id.strip():
            raise ValueError("rule_id must be a non-empty string")
        object.__setattr__(self, "rule_id", self.rule_id.strip())

        if not isinstance(self.kind, str) or self.kind.strip().lower() not in VALID_ALERT_KINDS:
            raise ValueError(f"kind must be one of: {', '.join(VALID_ALERT_KINDS)}")
        object.__setattr__(self, "kind", self.kind.strip().lower())

        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        object.__setattr__(self, "symbol", self.symbol.strip())

        if (
            not isinstance(self.condition_type, str)
            or self.condition_type.strip().lower() not in VALID_CONDITION_TYPES
        ):
            raise ValueError(f"condition_type must be one of: {', '.join(VALID_CONDITION_TYPES)}")
        object.__setattr__(self, "condition_type", self.condition_type.strip().lower())

        if not isinstance(self.timeframe, str) or not self.timeframe.strip():
            raise ValueError("timeframe must be a non-empty string")
        object.__setattr__(self, "timeframe", self.timeframe.strip())

        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")

        if self.threshold is not None:
            if isinstance(self.threshold, bool) or not isinstance(self.threshold, (int, float)):
                raise ValueError("threshold must be a numeric value")
            if not math.isfinite(self.threshold):
                raise ValueError("threshold must be finite")
            object.__setattr__(self, "threshold", float(self.threshold))

        if self.expected_value is not None:
            if not isinstance(self.expected_value, str):
                raise ValueError("expected_value must be a string")
            object.__setattr__(self, "expected_value", self.expected_value.strip())

        if (
            isinstance(self.created_at, bool)
            or not isinstance(self.created_at, (int, float, str))
        ):
            raise ValueError("created_at must be an int, float, or ISO string")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "kind": self.kind,
            "symbol": self.symbol,
            "condition_type": self.condition_type,
            "threshold": self.threshold,
            "expected_value": self.expected_value,
            "timeframe": self.timeframe,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class MarketAlert:
    """Immutable user-facing alert derived from real monitored state."""

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
            raise ValueError("created_at must be an int, float, or ISO-formatted string")
        if isinstance(self.created_at, str) and not self.created_at.strip():
            raise ValueError("created_at string must not be empty or whitespace")
        if isinstance(self.created_at, (int, float)) and not math.isfinite(self.created_at):
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

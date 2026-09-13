"""Provider capability and health validation application service.

Explicit, read-side validation over the existing ProviderAccess boundary.
It observes one requested provider (or every registered provider) and
returns a structured result. It does not replace ProviderAccess,
ProviderRegistry, ProviderResolver, ProviderOperations, or
ProviderInspectionService.

Rules:
- provider identity is always explicit: category + provider id
- no fallback, no switching, no singleton, no hidden state
- construction and validation never call connect(), fetch_*, or close()
- the only provider method executed is describe(), which the port
  contract requires to be I/O-free
- unknown/unregistered providers return an explicit unavailable result
  instead of substituting another provider
- capabilities come from existing category contracts and provider/metadata
  reports; they are never fabricated
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

from src.platform.domain.availability import VALID_STATUSES
from src.platform.services.provider_access import ProviderAccess
from src.platform.services.provider_registry import (
    CATEGORY_MARKET_DATA,
    CATEGORY_QUOTE,
    InvalidProviderRegistrationError,
    ProviderRecord,
    ProviderRegistryError,
    UnknownProviderCategoryError,
    UnknownProviderError,
)

AVAILABILITY_AVAILABLE = "available"
AVAILABILITY_UNAVAILABLE = "unavailable"

HEALTH_HEALTHY = "healthy"
HEALTH_UNHEALTHY = "unhealthy"
HEALTH_UNAVAILABLE = "unavailable"
HEALTH_UNKNOWN = "unknown"

REASON_PROVIDER_NOT_REGISTERED = "provider not registered"
REASON_PROVIDER_CANNOT_BE_RESOLVED = "provider cannot be resolved"
REASON_REQUIRED_CAPABILITY_UNAVAILABLE = "required capability unavailable"
REASON_PROVIDER_METADATA_INVALID = "provider metadata invalid"
REASON_PROVIDER_CONTRACT_UNAVAILABLE = "provider contract unavailable"
REASON_PROVIDER_OPERATION_FAILED = "provider operation failed"

_UNHEALTHY_REPORTED = frozenset(
    {
        "unavailable",
        "unhealthy",
        "error",
        "offline",
        "disconnected",
        "closed",
    }
)
_HEALTHY_REPORTED = frozenset(
    {
        "healthy",
        "available",
        "connected",
        "live",
    }
)
_REPORTED_STATUSES = frozenset(_UNHEALTHY_REPORTED | _HEALTHY_REPORTED | {"unknown", "stale"}) | frozenset(
    VALID_STATUSES
)


@dataclass(frozen=True)
class ProviderValidationResult:
    """Structured validation of one explicitly identified provider."""

    category: str
    provider_id: str
    availability: str
    health: str
    supports_candles: bool
    supports_quotes: bool
    reason: Optional[str] = None
    name: Optional[str] = None
    supported_symbols: Tuple[str, ...] = ()
    supported_timeframes: Tuple[str, ...] = ()
    capabilities: Dict[str, Any] = None  # type: ignore[assignment]
    metadata: Dict[str, Any] = None  # type: ignore[assignment]
    reported_status: Optional[str] = None
    detail: Optional[str] = None

    def __post_init__(self) -> None:
        if self.capabilities is None:
            object.__setattr__(self, "capabilities", {})
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "provider_id": self.provider_id,
            "availability": self.availability,
            "health": self.health,
            "supports_candles": self.supports_candles,
            "supports_quotes": self.supports_quotes,
            "reason": self.reason,
            "name": self.name,
            "supported_symbols": list(self.supported_symbols),
            "supported_timeframes": list(self.supported_timeframes),
            "capabilities": dict(self.capabilities),
            "metadata": dict(self.metadata),
            "reported_status": self.reported_status,
            "detail": self.detail,
        }


class ProviderValidationService:
    """Application validation boundary over an injected ProviderAccess.

    Construction and validation perform no connect/fetch/close. Unknown
    providers produce an unavailable result for the requested identity.
    """

    def __init__(self, access: ProviderAccess) -> None:
        if access is None or not isinstance(access, ProviderAccess):
            raise ValueError("access must be a ProviderAccess")
        self._access = access

    def validate(self, category: str, provider_id: str) -> ProviderValidationResult:
        """Validate one explicitly selected provider."""
        requested_category, requested_id = _requested_identity(category, provider_id)
        try:
            record = self._access.get_record(category, provider_id)
        except UnknownProviderError as exc:
            return _unavailable_result(
                category=requested_category,
                provider_id=requested_id,
                reason=REASON_PROVIDER_NOT_REGISTERED,
                detail=str(exc),
            )
        except UnknownProviderCategoryError as exc:
            return _unavailable_result(
                category=requested_category,
                provider_id=requested_id,
                reason=REASON_PROVIDER_CANNOT_BE_RESOLVED,
                detail=str(exc),
            )
        except InvalidProviderRegistrationError as exc:
            return _unavailable_result(
                category=requested_category,
                provider_id=requested_id,
                reason=REASON_PROVIDER_CANNOT_BE_RESOLVED,
                detail=str(exc),
            )
        except ProviderRegistryError as exc:
            return _unavailable_result(
                category=requested_category,
                provider_id=requested_id,
                reason=REASON_PROVIDER_CANNOT_BE_RESOLVED,
                detail=str(exc),
            )
        return self._validate_record(record)

    def validate_all(self) -> Tuple[ProviderValidationResult, ...]:
        """Validate every registered provider. Empty registry returns ()."""
        return tuple(
            self._validate_record(record) for record in self._access.list_providers()
        )

    def _validate_record(self, record: ProviderRecord) -> ProviderValidationResult:
        raw: Dict[str, Any]
        describe_error: Optional[str] = None
        try:
            described = record.provider.describe()
            if not isinstance(described, dict):
                raise TypeError(
                    f"describe() must return a dict, got {type(described).__name__}"
                )
            raw = dict(described)
        except Exception as exc:
            raw = {}
            describe_error = f"{type(exc).__name__}: {exc}"

        metadata = dict(record.metadata) if isinstance(record.metadata, dict) else {}
        if record.metadata is not None and not isinstance(record.metadata, dict):
            return ProviderValidationResult(
                category=record.category,
                provider_id=record.provider_id,
                availability=AVAILABILITY_AVAILABLE,
                health=HEALTH_UNHEALTHY,
                supports_candles=False,
                supports_quotes=False,
                reason=REASON_PROVIDER_METADATA_INVALID,
                capabilities=raw,
                metadata={},
                detail="provider metadata must be a dict",
            )

        name = _first_str(raw.get("name"), metadata.get("name"))
        supports_candles = _capability_flag(
            capabilities=raw,
            metadata=metadata,
            key="supports_fetch_candles",
            default=record.category == CATEGORY_MARKET_DATA,
        )
        supports_quotes = _capability_flag(
            capabilities=raw,
            metadata=metadata,
            key="supports_fetch_quote",
            default=record.category == CATEGORY_QUOTE,
        )
        required_missing = (
            record.category == CATEGORY_MARKET_DATA and not supports_candles
        ) or (record.category == CATEGORY_QUOTE and not supports_quotes)

        reported = _first_str(
            _first_scalar(raw.get("status"), metadata.get("status")),
            _availability_status(raw),
            _availability_status(metadata),
        )
        reported_reason = _first_str(
            _availability_reason(raw),
            _availability_reason(metadata),
            _first_scalar(raw.get("reason"), metadata.get("reason")),
        )

        if describe_error is not None:
            health = HEALTH_UNHEALTHY
            reason = REASON_PROVIDER_OPERATION_FAILED
            detail = describe_error
        elif required_missing:
            health = HEALTH_UNHEALTHY
            reason = REASON_REQUIRED_CAPABILITY_UNAVAILABLE
            detail = reported_reason
        else:
            health = _health_from_reported(reported)
            if health == HEALTH_UNHEALTHY:
                reason = reported_reason or REASON_PROVIDER_CONTRACT_UNAVAILABLE
            else:
                reason = reported_reason
            detail = None

        return ProviderValidationResult(
            category=record.category,
            provider_id=record.provider_id,
            availability=AVAILABILITY_AVAILABLE,
            health=health,
            supports_candles=supports_candles,
            supports_quotes=supports_quotes,
            reason=reason,
            name=name,
            supported_symbols=_string_tuple(
                _first_seq(raw.get("supported_symbols"), metadata.get("supported_symbols"))
            ),
            supported_timeframes=_string_tuple(
                _first_seq(
                    raw.get("supported_timeframes"),
                    metadata.get("supported_timeframes"),
                )
            ),
            capabilities=raw,
            metadata=metadata,
            reported_status=reported,
            detail=detail,
        )


def _requested_identity(category: Any, provider_id: Any) -> Tuple[str, str]:
    category_text = category.strip() if isinstance(category, str) else str(category)
    provider_text = (
        provider_id.strip() if isinstance(provider_id, str) else str(provider_id)
    )
    return category_text, provider_text


def _unavailable_result(
    category: str,
    provider_id: str,
    reason: str,
    detail: Optional[str],
) -> ProviderValidationResult:
    return ProviderValidationResult(
        category=category,
        provider_id=provider_id,
        availability=AVAILABILITY_UNAVAILABLE,
        health=HEALTH_UNAVAILABLE,
        supports_candles=False,
        supports_quotes=False,
        reason=reason,
        detail=detail,
    )


def _health_from_reported(reported: Optional[str]) -> str:
    if reported is None:
        return HEALTH_UNKNOWN
    normalized = reported.strip().lower()
    if normalized in _UNHEALTHY_REPORTED:
        return HEALTH_UNHEALTHY
    if normalized in _HEALTHY_REPORTED:
        return HEALTH_HEALTHY
    if normalized in _REPORTED_STATUSES:
        return HEALTH_UNKNOWN
    return HEALTH_UNKNOWN


def _availability_status(payload: Dict[str, Any]) -> Optional[str]:
    availability = payload.get("availability")
    if isinstance(availability, dict):
        status = availability.get("status")
        if isinstance(status, str) and status.strip():
            return status.strip()
    return None


def _availability_reason(payload: Dict[str, Any]) -> Optional[str]:
    availability = payload.get("availability")
    if isinstance(availability, dict):
        reason = availability.get("reason")
        if isinstance(reason, str) and reason.strip():
            return reason.strip()
    return None


def _first_scalar(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _first_str(*values: Any) -> Optional[str]:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_seq(*values: Any) -> Optional[Sequence[Any]]:
    for value in values:
        if isinstance(value, (list, tuple, set)):
            return value
    return None


def _capability_flag(
    capabilities: Dict[str, Any],
    metadata: Dict[str, Any],
    key: str,
    default: bool,
) -> bool:
    override = _first_scalar(capabilities.get(key), metadata.get(key))
    if isinstance(override, bool):
        return override
    return default


def _string_tuple(value: Optional[Sequence[Any]]) -> Tuple[str, ...]:
    if value is None:
        return ()
    seen: list = []
    for item in value:
        if isinstance(item, str) and item.strip() and item.strip() not in seen:
            seen.append(item.strip())
    return tuple(seen)

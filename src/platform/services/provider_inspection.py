"""Provider capability/health inspection application service.

Read-side, application-level capability that reports what provider are
registered, what each provider's own ``describe()`` contract says, what
capabilities (fetch candles/fetch quote/supported symbols/timeframes
are statically supported, and the provider's reported health/status when the
provider or its registration metadata literally reports one.

Rules:
- provider identity stays explicit: category + provider id, never collapsed
- construction and ``inspect*`` never call connect(), fetch_*, or close()
- the only provider method executed is ``describe()``,, which the port contract
  requires to be I/O-free (construction/import/describe MUST NOT do I/O)
- no fallback, no switching, no hidden retry, no auto-connect
- no fabrication: when a capability/status/reason is not reported it stays
  unset (None/empty/unknown), never invented from the provider object
- provider ``describe()`` exceptions are never swallowed into fake success:
  they surface as a distinct ``error`` health state carrying the original
  diagnostic string (no exception is hidden or converted to healthy)
- unknown providers/categories propagate the registry errors as-is
- no dependency on concrete provider implementations or the original engine
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

from src.platform.domain.availability import VALID_STATUSES
from src.platform.services.provider_access import ProviderAccess
from src.platform.services.provider_registry import (
    CATEGORY_MARKET_DATA,
    CATEGORY_QUOTE,
    UnknownProviderError,
)

HEALTH_STATUS_AVAILABLE = "available"
HEALTH_STATUS_UNAVAILABLE = "unavailable"
HEALTH_STATUS_CONNECTED = "connected"
HEALTH_STATUS_DISCONNECTED = "disconnected"
HEALTH_STATUS_ERROR = "error"
HEALTH_STATUS_UNKNOWN = "unknown"

_REPORTED_STATUSES: Tuple[str, ...] = (
    HEALTH_STATUS_AVAILABLE,
    HEALTH_STATUS_UNAVAILABLE,
    HEALTH_STATUS_CONNECTED,
    HEALTH_STATUS_DISCONNECTED,
    HEALTH_STATUS_ERROR,
    HEALTH_STATUS_UNKNOWN,
) + tuple(VALID_STATUSES)


@dataclass(frozen=True)
class ProviderCapability:
    """Static, serializable capability snapshot for one explicit provider.

    ``capabilities`` is the provider's own ``describe()`` payload (verbatim);
    ``metadata`` is the registration metadata (verbatim). Capability flags come
    from the provider category contract unless the provider/metadata literally
    reports a boolean override. Supported symbol/timeframe lists appear only
    when the provider or metadata literally reports them.
    """

    category: str
    provider_id: str
    name: Optional[str] = None
    capabilities: Dict[str, Any] = None  # type: ignore[assignment]
    metadata: Dict[str, Any] = None  # type: ignore[assignment]
    supports_fetch_candles: bool = False
    supports_fetch_quote: bool = False
    supported_symbols: Tuple[str, ...] = ()
    supported_timeframes: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.capabilities is None:
            object.__setattr__(self, "capabilities", {})
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "provider_id": self.provider_id,
            "name": self.name,
            "capabilities": dict(self.capabilities),
            "metadata": dict(self.metadata),
            "supports_fetch_candles": self.supports_fetch_candles,
            "supports_fetch_quote": self.supports_fetch_quote,
            "supported_symbols": list(self.supported_symbols),
            "supported_timeframes": list(self.supported_timeframes),
        }


@dataclass(frozen=True)
class ProviderHealth:
    """Reported provider health/status for one explicit provider.



    ``status`` is the normalized canonical status (one of the HEALTH_STATUS_*
    values or the domain Availability statuses). ``reported_status`` preserves
    the raw status string the provider/metadata reported. ``reason`` carries a
    reported reason when one was supplied. ``error`` carries the diagnostic
    string when ``describe()`` failed,, so a real provider error is never
    disguised as a healthy result..
    """

    category: str
    provider_id: str
    status: str = HEALTH_STATUS_UNKNOWN
    reported_status: Optional[str] = None
    reason: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "provider_id": self.provider_id,
            "status": self.status,
            "reported_status": self.reported_status,
            "reason": self.reason,
            "error": self.error,
        }


@dataclass(frozen=True)
class ProviderInspection:
    """Combined capability/health inspection for one explicit provider."""

    category: str
    provider_id: str
    capability: ProviderCapability
    health: ProviderHealth

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "provider_id": self.provider_id,
            "capability": self.capability.to_dict(),
            "health": self.health.to_dict(),
        }


class ProviderInspectionService:
    """Application service inspecting registered provider capabilities and health.



    Lifecycle: inspection is read-side. It never connects, fetches,,or
    closes providers;; the only provider method it executes is ``describe()``
    (a no-I/O contract). Callers who need live connectivity must drive the
    explicit lifecycle themselves via ProviderAccess/ProviderWorkflow.



    Construction validation (no I/O): inject a ProviderAccess.. Registry/unknown
    errors and provider ``describe()`` errors are reported honestly(as-is or an
    explicit error health state), never as fabricated success..
    """

    def __init__(self, access: ProviderAccess) -> None:
        if access is None or not isinstance(access, ProviderAccess):
            raise ValueError("access must be a ProviderAccess")
        self._access = access

    def inspect(self, category: str, provider_id: str) -> ProviderInspection:
        """Inspect one explicitly selected provider (no I/O beyond describe())."""

        provider = self._access.resolve_provider(category, provider_id)
        record = None
        for candidate in self._access.list_providers():
            if candidate.provider is provider:
                record = candidate
                break
        if record is None:
            raise UnknownProviderError(
                f"unknown provider {provider_id!r} in category {category!r}"
            )
        return self._build(
            category=record.category,
            provider_id=record.provider_id,
            provider=record.provider,
            metadata=record.metadata,
        )

    def inspect_all(self) -> Tuple[ProviderInspection, ...]:
        """Inspect every registered provider, kept in explicit category+id records.


        Provider identity remains explicit::the results never collapse the two
        provider roles into one ambiguous value..
        """
        return tuple(
            self._build(
                category=record.category,
                provider_id=record.provider_id,
                provider=record.provider,
                metadata=record.metadata,
            )
            for record in self._access.list_providers()
        )

    def _build(
        self,
        category: str,
        provider_id: str,
        provider: Any,
        metadata: Dict[str, Any],
    ) -> ProviderInspection:
        raw: Dict[str, Any]
        error: Optional[str] = None
        try:
            raw = provider.describe()
            if not isinstance(raw, dict):
                raise TypeError(
                    f"describe() must return a dict, got {type(raw).__name__}"
                )
        except Exception as exc:
            raw = {}
            error = f"{type(exc).__name__}: {exc}"
        capabilities = dict(raw)
        reported_name = _first_str(
            capabilities.get("name"), metadata.get("name")
        )
        supports_candles = _capability_flag(
            capabilities=capabilities,
            metadata=metadata,
            key="supports_fetch_candles",
            default=category == CATEGORY_MARKET_DATA,
        )
        supports_quote = _capability_flag(
            capabilities=capabilities,
            metadata=metadata,
            key="supports_fetch_quote",
            default=category == CATEGORY_QUOTE,
        )
        supported_symbols = _string_tuple(
            _first_seq(capabilities.get("supported_symbols"), metadata.get("supported_symbols"))
        )
        supported_timeframes = _string_tuple(
            _first_seq(
                capabilities.get("supported_timeframes"),
                metadata.get("supported_timeframes"),
            )
        )
        capability = ProviderCapability(
            category=category,
            provider_id=provider_id,
            name=reported_name,
            capabilities=capabilities,
            metadata=dict(metadata),
            supports_fetch_candles=supports_candles,
            supports_fetch_quote=supports_quote,
            supported_symbols=supported_symbols,
            supported_timeframes=supported_timeframes,
        )
        health = self._build_health(
            category=category,
            provider_id=provider_id,
            capabilities=capabilities,
            metadata=metadata,
            error=error,
        )
        return ProviderInspection(
            category=category,
            provider_id=provider_id,
            capability=capability,
            health=health,
        )

    def _build_health(
        self,
        category: str,
        provider_id: str,
        capabilities: Dict[str, Any],
        metadata: Dict[str, Any],
        error: Optional[str] = None,
    ) -> ProviderHealth:
        if error is not None:
            return ProviderHealth(
                category=category,
                provider_id=provider_id,
                status=HEALTH_STATUS_ERROR,
                error=error,
            )
        reported = _first_str(
            _first_scalar(capabilities.get("status"), metadata.get("status")),
            _availability_status(capabilities),
            _availability_status(metadata),
        )
        status = _normalize_status(reported)
        reason = _first_str(
            _availability_reason(capabilities),
            _availability_reason(metadata),
            _first_scalar(capabilities.get("reason"), metadata.get("reason")),
        )
        return ProviderHealth(
            category=category,
            provider_id=provider_id,
            status=status,
            reported_status=reported,
            reason=reason,
        )


def _normalize_status(reported: Optional[str]) -> str:
    if reported is None:
        return HEALTH_STATUS_UNKNOWN
    normalized = reported.strip().lower()
    if normalized in _REPORTED_STATUSES:

        return normalized
    return HEALTH_STATUS_UNKNOWN


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
"""Provider readiness application service (Part 13: Operational Gate).

Evaluates operational provider readiness by composing existing ProviderAccess,
ProviderValidationService, and ProviderMonitor services without duplicating
logic.

Distinguishes operational provider readiness (READY / NOT READY) from
trade-signal readiness and static capabilities.

Rules:
- Reuse existing health, validation, inspection, and monitoring logic.
- Provide deterministic READY / NOT READY verdicts.
- Provide explainable, deterministic reason for results.
- Support a single provider and all registered providers via existing registry.
- Do not make network calls or connect during construction.
"""

from typing import Any, Dict, Optional, Tuple, Union

from src.platform.domain.freshness import DataFreshness
from src.platform.domain.provider_readiness import (
    PROVIDER_STATUS_NOT_READY,
    PROVIDER_STATUS_READY,
    ProviderReadiness,
)
from src.platform.services.provider_access import ProviderAccess
from src.platform.services.provider_monitoring import (
    FRESH,
    STALE,
    UNAVAILABLE as MONITOR_UNAVAILABLE,
    ProviderMonitor,
    _age_seconds,
)
from src.platform.services.provider_operations import ProviderOperations
from src.platform.services.provider_registry import (
    CATEGORY_MARKET_DATA,
    CATEGORY_QUOTE,
)
from src.platform.services.provider_validation import (
    AVAILABILITY_UNAVAILABLE,
    HEALTH_HEALTHY,
    HEALTH_UNHEALTHY,
    REASON_PROVIDER_CANNOT_BE_RESOLVED,
    REASON_PROVIDER_CONTRACT_UNAVAILABLE,
    REASON_PROVIDER_METADATA_INVALID,
    REASON_PROVIDER_NOT_REGISTERED,
    REASON_PROVIDER_OPERATION_FAILED,
    REASON_REQUIRED_CAPABILITY_UNAVAILABLE,
    ProviderValidationService,
)

REASON_READY = "provider is operational and ready"
REASON_PROVIDER_UNAVAILABLE = "provider is unavailable"
REASON_PROVIDER_UNHEALTHY = "provider is unhealthy"
REASON_CAPABILITY_MISSING = "required capability unavailable"
REASON_DATA_STALE = "provider market data is stale"
REASON_QUOTE_UNAVAILABLE = "provider quote is unavailable"
REASON_FRESHNESS_UNKNOWN = "provider data freshness unknown"


class ProviderReadinessService:
    """Application service for determining provider operational readiness."""

    def __init__(
        self,
        access: ProviderAccess,
        monitor: Optional[ProviderMonitor] = None,
    ) -> None:
        if access is None or not isinstance(access, ProviderAccess):
            raise ValueError("access must be a ProviderAccess instance")
        if monitor is not None and not isinstance(monitor, ProviderMonitor):
            raise ValueError("monitor must be a ProviderMonitor instance when provided")

        self._access = access
        self._validation_service = ProviderValidationService(access)
        self._monitor = monitor
        self._operations = ProviderOperations(access)

    @property
    def access(self) -> ProviderAccess:
        """Return injected ProviderAccess."""
        return self._access

    def assess(
        self,
        category: str,
        provider_id: str,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        reference: Optional[Union[int, float, str]] = None,
        max_age_seconds: float = 60.0,
        market_data_provider_id: Optional[str] = None,
    ) -> ProviderReadiness:
        """Assess operational readiness for one explicitly requested provider."""

        validation = self._validation_service.validate(category, provider_id)

        # 1. Unregistered / unavailable provider check
        if validation.availability == AVAILABILITY_UNAVAILABLE:
            reason = (
                validation.reason
                if validation.reason in (REASON_PROVIDER_NOT_REGISTERED, REASON_PROVIDER_CANNOT_BE_RESOLVED)
                else REASON_PROVIDER_UNAVAILABLE
            )
            return ProviderReadiness(
                category=category,
                provider_id=provider_id,
                status=PROVIDER_STATUS_NOT_READY,
                reason=reason,
                health=validation.health,
                capabilities=validation.capabilities,
                metadata=validation.metadata,
                detail=validation.detail,
            )

        # 2. Missing required capability check
        if validation.reason == REASON_REQUIRED_CAPABILITY_UNAVAILABLE:
            return ProviderReadiness(
                category=validation.category,
                provider_id=validation.provider_id,
                status=PROVIDER_STATUS_NOT_READY,
                reason=REASON_CAPABILITY_MISSING,
                health=validation.health,
                capabilities=validation.capabilities,
                metadata=validation.metadata,
                detail=validation.detail,
            )

        # 3. Unhealthy check
        if validation.health == HEALTH_UNHEALTHY:
            reason = (
                validation.reason
                if validation.reason and validation.reason not in (
                    REASON_PROVIDER_OPERATION_FAILED,
                    REASON_PROVIDER_CONTRACT_UNAVAILABLE,
                )
                else REASON_PROVIDER_UNHEALTHY
            )
            return ProviderReadiness(
                category=validation.category,
                provider_id=validation.provider_id,
                status=PROVIDER_STATUS_NOT_READY,
                reason=reason,
                health=validation.health,
                capabilities=validation.capabilities,
                metadata=validation.metadata,
                detail=validation.detail,
            )

        # 4. Data freshness check (when symbol is provided)
        freshness_dict = None
        if symbol is not None:
            tf = timeframe if timeframe is not None else "1h"

            if validation.category == CATEGORY_MARKET_DATA and self._monitor is not None:
                try:
                    snapshot = self._monitor.monitor(
                        symbol=symbol,
                        timeframe=tf,
                        market_data_provider_id=validation.provider_id,
                        max_age_seconds=max_age_seconds,
                        reference=reference,
                    )
                    freshness_dict = snapshot.to_dict()

                    if snapshot.freshness is not None:
                        if snapshot.freshness.status == STALE:
                            return ProviderReadiness(
                                category=validation.category,
                                provider_id=validation.provider_id,
                                status=PROVIDER_STATUS_NOT_READY,
                                reason=REASON_DATA_STALE,
                                health=validation.health,
                                freshness=freshness_dict,
                                capabilities=validation.capabilities,
                                metadata=validation.metadata,
                                detail=snapshot.freshness.reason or "market data exceeds max allowed age",
                            )
                        if snapshot.freshness.status == MONITOR_UNAVAILABLE:
                            return ProviderReadiness(
                                category=validation.category,
                                provider_id=validation.provider_id,
                                status=PROVIDER_STATUS_NOT_READY,
                                reason=REASON_PROVIDER_UNAVAILABLE,
                                health=validation.health,
                                freshness=freshness_dict,
                                capabilities=validation.capabilities,
                                metadata=validation.metadata,
                                detail=snapshot.freshness.reason or "market data provider reported unavailable",
                            )
                except Exception as exc:
                    return ProviderReadiness(
                        category=validation.category,
                        provider_id=validation.provider_id,
                        status=PROVIDER_STATUS_NOT_READY,
                        reason=REASON_PROVIDER_UNHEALTHY,
                        health=validation.health,
                        capabilities=validation.capabilities,
                        metadata=validation.metadata,
                        detail=f"monitoring failed: {exc}",
                    )

            elif validation.category == CATEGORY_QUOTE:
                if self._monitor is not None and market_data_provider_id is not None:
                    try:
                        snapshot = self._monitor.monitor(
                            symbol=symbol,
                            timeframe=tf,
                            market_data_provider_id=market_data_provider_id,
                            quote_provider_id=validation.provider_id,
                            max_age_seconds=max_age_seconds,
                            reference=reference,
                        )
                        freshness_dict = snapshot.to_dict()
                        if snapshot.freshness is not None:
                            if snapshot.freshness.status == MONITOR_UNAVAILABLE:
                                return ProviderReadiness(
                                    category=validation.category,
                                    provider_id=validation.provider_id,
                                    status=PROVIDER_STATUS_NOT_READY,
                                    reason=REASON_QUOTE_UNAVAILABLE,
                                    health=validation.health,
                                    freshness=freshness_dict,
                                    capabilities=validation.capabilities,
                                    metadata=validation.metadata,
                                    detail=snapshot.freshness.reason or "quote provider reported market unavailable",
                                )
                            if snapshot.freshness.status == STALE:
                                return ProviderReadiness(
                                    category=validation.category,
                                    provider_id=validation.provider_id,
                                    status=PROVIDER_STATUS_NOT_READY,
                                    reason=REASON_DATA_STALE,
                                    health=validation.health,
                                    freshness=freshness_dict,
                                    capabilities=validation.capabilities,
                                    metadata=validation.metadata,
                                    detail=snapshot.freshness.reason or "quote exceeds max allowed age",
                                )
                    except Exception as exc:
                        return ProviderReadiness(
                            category=validation.category,
                            provider_id=validation.provider_id,
                            status=PROVIDER_STATUS_NOT_READY,
                            reason=REASON_PROVIDER_UNHEALTHY,
                            health=validation.health,
                            capabilities=validation.capabilities,
                            metadata=validation.metadata,
                            detail=f"monitoring failed: {exc}",
                        )
                else:
                    try:
                        quote_res = self._operations.fetch_quote(
                            provider_id=validation.provider_id,
                            symbol=symbol,
                        )
                        quote = quote_res.quote
                        quote_age = _age_seconds(quote.timestamp, reference) if reference is not None else None
                        is_unavail = (
                            quote.availability is not None
                            and quote.availability.status == "unavailable"
                        )
                        freshness_status = (
                            "unavailable"
                            if is_unavail
                            else (
                                "stale"
                                if quote_age is not None and quote_age > max_age_seconds
                                else "fresh"
                            )
                        )
                        freshness_obj = DataFreshness(
                            symbol=symbol,
                            timeframe=tf,
                            status=freshness_status,
                            reference_timestamp=reference,
                            quote_timestamp=quote.timestamp,
                            quote_age_seconds=quote_age,
                            reason=quote.availability.reason if is_unavail and quote.availability else None,
                        )
                        freshness_dict = {
                            "symbol": symbol,
                            "timeframe": tf,
                            "quote_provider_id": validation.provider_id,
                            "freshness": freshness_obj.to_dict(),
                            "quote_status": quote.availability.status if quote.availability else None,
                        }

                        if is_unavail:
                            return ProviderReadiness(
                                category=validation.category,
                                provider_id=validation.provider_id,
                                status=PROVIDER_STATUS_NOT_READY,
                                reason=REASON_QUOTE_UNAVAILABLE,
                                health=validation.health,
                                freshness=freshness_dict,
                                capabilities=validation.capabilities,
                                metadata=validation.metadata,
                                detail=quote.availability.reason if quote.availability else "quote provider reported market unavailable",
                            )
                        if freshness_status == "stale":
                            return ProviderReadiness(
                                category=validation.category,
                                provider_id=validation.provider_id,
                                status=PROVIDER_STATUS_NOT_READY,
                                reason=REASON_DATA_STALE,
                                health=validation.health,
                                freshness=freshness_dict,
                                capabilities=validation.capabilities,
                                metadata=validation.metadata,
                                detail="quote data exceeds max allowed age",
                            )
                    except Exception as exc:
                        return ProviderReadiness(
                            category=validation.category,
                            provider_id=validation.provider_id,
                            status=PROVIDER_STATUS_NOT_READY,
                            reason=REASON_PROVIDER_UNHEALTHY,
                            health=validation.health,
                            capabilities=validation.capabilities,
                            metadata=validation.metadata,
                            detail=f"fetch_quote failed: {exc}",
                        )

        # 5. Default READY
        return ProviderReadiness(
            category=validation.category,
            provider_id=validation.provider_id,
            status=PROVIDER_STATUS_READY,
            reason=REASON_READY,
            health=validation.health,
            freshness=freshness_dict,
            capabilities=validation.capabilities,
            metadata=validation.metadata,
            detail=validation.detail,
        )

    def assess_all(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        reference: Optional[Union[int, float, str]] = None,
        max_age_seconds: float = 60.0,
        market_data_provider_id: Optional[str] = None,
    ) -> Tuple[ProviderReadiness, ...]:
        """Assess operational readiness for all registered providers in the registry."""
        records = self._access.list_providers()
        return tuple(
            self.assess(
                category=record.category,
                provider_id=record.provider_id,
                symbol=symbol,
                timeframe=timeframe,
                reference=reference,
                max_age_seconds=max_age_seconds,
                market_data_provider_id=market_data_provider_id,
            )
            for record in records
        )

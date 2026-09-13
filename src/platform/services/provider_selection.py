"""Provider selection application service (Part 14: Operational Routing).

Selects an operationally READY provider from registered providers by delegating
readiness evaluations to the existing ProviderReadinessService boundary.

Deterministic Policy:
1. Evaluate registered providers in category.
2. If an explicit preferred provider is specified:
   - If READY, select it.
   - If NOT READY or not registered, record rejection reason and continue to fallback.
3. Fall back to the first READY provider in explicit registry order.
4. If no provider is READY, return structured NOT_AVAILABLE result.
"""

from typing import Optional, Tuple, Union

from src.platform.domain.provider_selection import (
    SELECTION_STATUS_NOT_AVAILABLE,
    SELECTION_STATUS_SELECTED,
    ProviderSelection,
)
from src.platform.services.provider_readiness import ProviderReadinessService

REASON_PREFERRED_SELECTED = "preferred provider selected"
REASON_NO_READY_PROVIDER = "no ready provider available"


class ProviderSelectionService:
    """Application service for selecting operationally READY providers."""

    def __init__(self, readiness_service: ProviderReadinessService) -> None:
        if readiness_service is None or not isinstance(readiness_service, ProviderReadinessService):
            raise ValueError("readiness_service must be a ProviderReadinessService instance")
        self._readiness_service = readiness_service

    def select_provider(
        self,
        category: str,
        preferred_provider_id: Optional[str] = None,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        reference: Optional[Union[int, float, str]] = None,
        max_age_seconds: float = 60.0,
        market_data_provider_id: Optional[str] = None,
    ) -> ProviderSelection:
        """Deterministically select a READY provider for category."""

        if not isinstance(category, str) or not category.strip():
            raise ValueError("category must be a non-empty string")

        preferred_rejected_reason: Optional[str] = None
        preferred_id_clean: Optional[str] = None

        if preferred_provider_id is not None:
            if not isinstance(preferred_provider_id, str) or not preferred_provider_id.strip():
                raise ValueError("preferred_provider_id must be a non-empty string if provided")
            preferred_id_clean = preferred_provider_id.strip().lower()

            pref_readiness = self._readiness_service.assess(
                category=category,
                provider_id=preferred_id_clean,
                symbol=symbol,
                timeframe=timeframe,
                reference=reference,
                max_age_seconds=max_age_seconds,
                market_data_provider_id=market_data_provider_id,
            )

            if pref_readiness.is_ready:
                return ProviderSelection(
                    category=category,
                    status=SELECTION_STATUS_SELECTED,
                    reason=REASON_PREFERRED_SELECTED,
                    selected_provider_id=pref_readiness.provider_id,
                    preferred_provider_id=preferred_id_clean,
                    readiness=pref_readiness,
                    evaluated_readiness=(pref_readiness,),
                )
            else:
                preferred_rejected_reason = pref_readiness.reason

        # Fallback selection: list all registered providers in registry order using public readiness access property
        records = self._readiness_service.access.list_providers(category=category)
        evaluated = []

        for record in records:
            if preferred_id_clean and record.provider_id == preferred_id_clean:
                continue

            r = self._readiness_service.assess(
                category=category,
                provider_id=record.provider_id,
                symbol=symbol,
                timeframe=timeframe,
                reference=reference,
                max_age_seconds=max_age_seconds,
                market_data_provider_id=market_data_provider_id,
            )
            evaluated.append(r)

            if r.is_ready:
                if preferred_id_clean:
                    reason = (
                        f"preferred provider '{preferred_id_clean}' rejected "
                        f"({preferred_rejected_reason}); fell back to ready provider '{r.provider_id}'"
                    )
                else:
                    reason = f"selected ready provider '{r.provider_id}'"

                return ProviderSelection(
                    category=category,
                    status=SELECTION_STATUS_SELECTED,
                    reason=reason,
                    selected_provider_id=r.provider_id,
                    preferred_provider_id=preferred_id_clean,
                    preferred_rejected_reason=preferred_rejected_reason,
                    readiness=r,
                    evaluated_readiness=tuple(evaluated),
                )

        # No READY provider found
        if preferred_id_clean:
            reason = (
                f"preferred provider '{preferred_id_clean}' rejected "
                f"({preferred_rejected_reason}) and no fallback ready provider available"
            )
        else:
            reason = f"{REASON_NO_READY_PROVIDER} for category '{category}'"

        return ProviderSelection(
            category=category,
            status=SELECTION_STATUS_NOT_AVAILABLE,
            reason=reason,
            selected_provider_id=None,
            preferred_provider_id=preferred_id_clean,
            preferred_rejected_reason=preferred_rejected_reason,
            readiness=None,
            evaluated_readiness=tuple(evaluated),
        )

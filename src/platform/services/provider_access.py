"""Application-layer provider access facade.

This is the smallest controlled way for higher-level application code to
explicitly resolve a market-data or quote provider. It composes the existing
ProviderRegistry and ProviderResolver and does not rebuild or duplicate them.

It does not:
- perform network I/O.
- register or invent providers.
- fall back to an implicit provider or switch automatically.
- connect(), fetch_*, or close() providers.
- import BiQuote or any concrete provider implementation
- touch the domain or the original AI-Trading-Lab engine.

Provider lifecycle (connect/fetch/close) remains entirely the caller's
responsibility. Resolution is a pure read-side lookup.
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

from src.platform.providers.market_data import MarketDataProvider
from src.platform.providers.quote import QuoteProvider
from src.platform.services.provider_registry import (
    ProviderRecord,
    ProviderRegistry,
    ProviderResolver,
)


class ProviderAccess:
    """Explicit, read-side access to providers registered in a ProviderRegistry.

    Composition:

    - inject a ProviderRegistry (no global singleton)
    - resolution goes through the existing ProviderResolver

    Guarantees:

    - construction and resolution never perform I/O, connect, fetch, close, or fallback
    - the caller owns every provider lifecycle (connect/fetch/close)
    - application code never depends on concrete provider implementations
    """

    def __init__(self, registry: ProviderRegistry) -> None:
        if registry is None or not isinstance(registry, ProviderRegistry):
            raise ValueError("registry must be a ProviderRegistry")
        self._registry = registry
        self._resolver = ProviderResolver(registry)

    def market_data_provider(self, provider_id: str) -> MarketDataProvider:
        """Resolve an explicit market-data provider. Raises on unknown id/category."""
        return self._resolver.resolve_market_data(provider_id)

    def quote_provider(self, provider_id: str) -> QuoteProvider:
        """Resolve an explicit quote provider. Raises on unknown id/category."""
        return self._resolver.resolve_quote(provider_id)

    def resolve_provider(self, category: str, provider_id: str) -> Any:
        """Generic explicit resolution by category/id."""
        return self._resolver.resolve(category, provider_id)

    def contains(self, category: str, provider_id: str) -> bool:
        """Return whether category/id is registered. Never falls back."""
        return self._resolver.contains(category, provider_id)

    def list_providers(self, category: Optional[str] = None) -> Tuple[ProviderRecord, ...]:
        """List registered provider records (sorted) without activating providers."""
        return self._resolver.list_records(category=category)

    def supported_categories(self) -> Tuple[str, ...]:
        """Return sorted tuple of supported provider categories."""
        return self._registry.supported_categories()

"""Provider-based market/quote application workflow.

Composes the application ProviderAccess layer with the existing adapters and
services to drive explicit, caller-owned provider operations. It does
not implement UI, API, WebSocket, signals, strategy, or any background
activity. Network activity may occur only when an explicit fetch/quote
operation is invoked; construction and resolution perform no I/O, no
connect, and no hidden fetch. Providers are never switched, replaced, or
fabricated: unknown ids/categories and provider errors propagate as-is.
"""
from dataclasses import dataclass
from typing import List

from src.platform.adapters.provider_adapter import ProviderAdapter
from src.platform.adapters.quote_adapter import QuoteAdapter
from src.platform.domain.market import Candle
from src.platform.domain.quote import Quote
from src.platform.providers.market_data import MarketDataProvider
from src.platform.providers.quote import QuoteProvider
from src.platform.services.market_data import MarketDataService
from src.platform.services.provider_access import ProviderAccess
from src.platform.services.quote import QuoteService


@dataclass(frozen=True)
class MarketDataHandle:
    """Explicitly resolved market-data provider and its selected identifier."""

    provider_id: str
    provider: MarketDataProvider


@dataclass(frozen=True)
class QuoteHandle:
    """Explicitly resolved quote provider and its selected identifier."""

    provider_id: str
    provider: QuoteProvider


@dataclass(frozen=True)
class CandleResult:
    """Market-data workflow result; carries the explicitly selected provider id."""

    provider_id: str
    candles: List[Candle]


@dataclass(frozen=True)
class QuoteResult:
    """Quote workflow result; carries the explicitly selected provider id."""

    provider_id: str
    quote: Quote


class ProviderWorkflow:
    """Application workflow consuming the ProviderAccess layer.



    Lifecycle: constructing/resolving never connects or fetches. Fetch/quote
    operations act only on the explicitly selected provider and the caller remains
    responsible for connect()/close() lifecycle (which may be no-ops)."""


    def __init__(self, access: ProviderAccess) -> None:
        if access is None or not isinstance(access, ProviderAccess):
            raise ValueError("access must be a ProviderAccess")
        self._access = access

    def market_data(self, provider_id: str) -> MarketDataHandle:
        """Explicitly resolve a market-data provider (no connect, no fetch)."""
        return MarketDataHandle(provider_id=provider_id, provider=self._access.market_data_provider(provider_id))

    def quote(self, provider_id: str) -> QuoteHandle:
        """Explicitly resolve a quote provider (no connect, no fetch)."""
        return QuoteHandle(provider_id=provider_id, provider=self._access.quote_provider(provider_id))

    def resolve_provider(self, category: str, provider_id: str):
        """Generic explicit resolution by category/id for workflow callers."""
        return self._access.resolve_provider(category, provider_id)

    def get_candles(
        self,
        provider_id: str,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> CandleResult:
        """Fetch candles only from the explicitly selected market-data provider.



        No fallback, no retry, no auto-connect; provider errors propagate."""

        provider = self._access.market_data_provider(provider_id)
        adapter = ProviderAdapter(provider)
        service = MarketDataService(adapter)
        candles = service.get_candles(symbol=symbol, timeframe=timeframe, limit=limit)
        return CandleResult(provider_id=provider_id, candles=candles)

    def get_quote(self, provider_id: str, symbol: str) -> QuoteResult:
        """Fetch a quote only from the explicitly selected quote provider.



        No fallback, no polling, no auto-connect; provider errors propagate."""

        provider = self._access.quote_provider(provider_id)
        adapter = QuoteAdapter(provider)
        service = QuoteService(adapter)
        quote = service.get_quote(symbol=symbol)
        return QuoteResult(provider_id=provider_id, quote=quote)

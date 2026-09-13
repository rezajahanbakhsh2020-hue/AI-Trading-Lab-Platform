"""Application provider operation layer.

Executes explicit provider-backed operations (candles and quotes) on top of
the ProviderAccess layer and existing adapters/services, while keeping a
strict, caller-owned boundary around I/Oand lifecycle.

Rules:
- provider selection is always explicit
- no hidden resolution, no fallback, no auto-connect, no auto-fetch
- construction, validation, and resolution perform no I/O
- network I/O happens only when an explicit fetch operation is executed
- provider identity is preserved in every result
- validation failures raise InvalidOperationError (deterministic)
- provider/service execution failures raise ProviderOperationFailure
  carrying provider id, category, operation, and the original cause
- unknown providers/categories raise the registry errors as-is
- no dependency on concrete provider implementations
"""

from dataclasses import dataclass
from typing import List

from src.platform.adapters.provider_adapter import ProviderAdapter
from src.platform.adapters.quote_adapter import QuoteAdapter
from src.platform.domain.market import Candle
from src.platform.domain.quote import Quote
from src.platform.services.market_data import MarketDataService, MAX_CANDLES
from src.platform.services.provider_access import ProviderAccess
from src.platform.services.provider_registry import (
    CATEGORY_MARKET_DATA,
    CATEGORY_QUOTE,
)
from src.platform.services.quote import QuoteService


class ProviderOperationError(Exception):
    """Base error for the application provider operation layer."""


class InvalidOperationError(ProviderOperationError):
    """Operation arguments failed deterministic validation."""


class ProviderOperationFailure(ProviderOperationError):
    """An explicit operation failed while executing provider/service work."""

    def __init__(
        self,
        provider_id: str,
        category: str,
        operation: str,
        cause: Exception,
    ) -> None:
        self.provider_id = provider_id
        self.category = category
        self.operation = operation
        self.cause = cause
        super().__init__(
            f"provider operation '{operation}' failed for provider "
            f"{provider_id!r} in category {category!r}: {cause}"
        )


@dataclass(frozen=True)
class CandleOperationResult:
    """Result of an explicit candle operation; echoes requested inputs."""

    provider_id: str
    symbol: str
    timeframe: str
    limit: int
    candles: List[Candle]


@dataclass(frozen=True)
class QuoteOperationResult:
    """Result of an explicit quote operation; echoes requested symbol."""

    provider_id: str
    symbol: str
    quote: Quote


class ProviderOperations:
    """Application operation layer executing explicit provider-backed operations."""

    def __init__(self, access: ProviderAccess) -> None:
        if access is None or not isinstance(access, ProviderAccess):
            raise ValueError("access must be a ProviderAccess")
        self._access = access

    def validate_candles_request(
        self,
        provider_id: str,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> None:
        """Deterministically validate a candle operation request (no I/O)."""
        _validate_provider_id(provider_id)
        _validate_symbol(symbol)
        _validate_timeframe(timeframe)
        _validate_limit(limit)

    def validate_quote_request(self, provider_id: str, symbol: str) -> None:
        """Deterministically validate a quote operation request (no I/O)."""
        _validate_provider_id(provider_id)
        _validate_symbol(symbol)

    def fetch_candles(
        self,
        provider_id: str,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> CandleOperationResult:
        """Execute an explicit candle operation on the selected provider."""

        self.validate_candles_request(provider_id, symbol, timeframe, limit)
        provider = self._access.market_data_provider(provider_id)
        try:
            service = MarketDataService(ProviderAdapter(provider))
            candles = service.get_candles(symbol=symbol, timeframe=timeframe, limit=limit)
        except Exception as exc:
            raise ProviderOperationFailure(
                provider_id=provider_id,
                category=CATEGORY_MARKET_DATA,
                operation="fetch_candles",
                cause=exc,
            ) from exc
        return CandleOperationResult(
            provider_id=provider_id,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            candles=candles,
        )

    def fetch_quote(self, provider_id: str, symbol: str) -> QuoteOperationResult:
        """Execute an explicit quote operation on the selected provider."""

        self.validate_quote_request(provider_id, symbol)
        provider = self._access.quote_provider(provider_id)
        try:
            service = QuoteService(QuoteAdapter(provider))
            quote = service.get_quote(symbol=symbol)
        except Exception as exc:
            raise ProviderOperationFailure(
                provider_id=provider_id,
                category=CATEGORY_QUOTE,
                operation="fetch_quote",
                cause=exc,
            ) from exc
        return QuoteOperationResult(
            provider_id=provider_id,
            symbol=symbol,
            quote=quote,
        )


def _validate_provider_id(provider_id: str) -> None:
    if not isinstance(provider_id, str):
        raise InvalidOperationError("provider_id must be a string")
    if provider_id.strip() == "":
        raise InvalidOperationError("provider_id must not be empty or whitespace")


def _validate_symbol(symbol: str) -> None:
    if not isinstance(symbol, str):
        raise InvalidOperationError("symbol must be a string")
    if symbol.strip() == "":
        raise InvalidOperationError("symbol must not be empty or whitespace")


def _validate_timeframe(timeframe: str) -> None:
    if not isinstance(timeframe, str):
        raise InvalidOperationError("timeframe must be a string")
    if timeframe.strip() == "":
        raise InvalidOperationError("timeframe must not be empty or whitespace")


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise InvalidOperationError("limit must be an integer")
    if limit <= 0:
        raise InvalidOperationError("limit must be greater than zero")
    if limit > MAX_CANDLES:
        raise InvalidOperationError(f"limit must be at most {MAX_CANDLES}")
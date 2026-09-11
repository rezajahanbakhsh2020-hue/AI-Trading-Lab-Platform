"""Market + quote consistency boundary.

Small explicit application-level boundary that combines one explicitly
selected market-data provider and one explicitly selected quote provider for
the same requested market context. It keeps the two provider identities
separately identifiable, refuses to fall back, switch,, or hide either
source, and rejects inconsistent result pairs clearly rather than returning a
seemingly-valid combined snapshot.

Rules:
- both providers are selected explicitly by the caller
- provider identities remain separately identifiable in the result
- no fallback, no surrogate, no hidden provider call, no background call
- no retry with provider switching: provider errors propagate as-is
- no fabrication: quotes are never synthesized from candles and candles are
  never synthesized from quotes; None/unavailable stays None/unavailable
- construction and validation perform no I/O; every fetch is explicit
- the smallest correctness rule: the requested symbol must match across
  the candle result and quote result,, because both operation results echo the
  requested market context;; a mismatch means the explicit combination is
  inconsistent and must fail clearly
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.platform.domain.availability import Availability
from src.platform.domain.market import Candle
from src.platform.domain.quote import Quote
from src.platform.services.provider_operations import ProviderOperations


class InconsistentMarketQuoteError(Exception):
    """Explicitly selected market-data and quote sources disagree on the market context.

    Raised deterministically when the candle result echoes a different symbol
    than the quote result for the same requested context;; it never resembles a
    successful market state and never falls back to another provider.
    """

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        market_data_provider_id: str,
        quote_provider_id: str,
        expected_symbol: str,
        actual_quote_symbol: str,
    ) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.market_data_provider_id = market_data_provider_id
        self.quote_provider_id = quote_provider_id
        self.expected_symbol = expected_symbol
        self.actual_quote_symbol = actual_quote_symbol
        super().__init__(
            "inconsistent market/quote sources for symbol "
            f"{expected_symbol!r}: market-data provider "
            f"{market_data_provider_id!r} echoed symbol {expected_symbol!r} "
            f"but quote provider {quote_provider_id!r} returned symbol "
            f"{actual_quote_symbol!r}"
        )


@dataclass(frozen=True)
class MarketQuoteResult:
    """Combined market+quote boundary result carrying both provider identities."""

    market_data_provider_id: str
    quote_provider_id: str
    symbol: str
    timeframe: str
    candles: List[Candle]
    quote: Quote
    availability: Optional[Availability] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "market_data_provider_id": self.market_data_provider_id,
            "quote_provider_id": self.quote_provider_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "candles": [c.to_dict() for c in self.candles],
            "quote": self.quote.to_dict(),
            "availability": None if self.availability is None else self.availability.to_dict(),
        }


class MarketQuoteConsistencyService:
    """Application boundary combining an explicit market-data provider anda
    an explicit quote provider for the same requested market context.


    The caller owns provider/source lifecycle. This service never connects,
    closes,, retries,, falls back,, or switches: every fetch is explicit through
    the injected ProviderOperations layer, and provider failures propagate
    unchanged. Invalid inputs are rejected before any I/O. When both
    explicit results agree on the requested context,, a MarketQuoteResult is
    returned carrying both identities separately;; otherwise an
    InconsistentMarketQuoteError is raised deterministically.

    Unavailable data remains unavailable(: Quote domain objects may carry an
    availability status of ``"unavailable"`` rather than prices;; that status is
    preserved verbatim, and never replaced with a synthesized price.``
    """

    def __init__(self, operations: ProviderOperations) -> None:
        if operations is None or not isinstance(operations, ProviderOperations):
            raise ValueError("operations must be a ProviderOperations")
        self._operations = operations

    def resolve(
        self,
        symbol: str,
        timeframe: str,
        market_data_provider_id: str,
        quote_provider_id: str,
        candles_limit: int = 100,
    ) -> MarketQuoteResult:
        """Resolve an explicit market-data+quote combination for one context.


        Raises:
        - validation errors (pre-I/O) for invalid inputs
        - InvalidOperationError from ProviderOperations for invalid requests
        - UnknownProviderError/UnknownProviderCategoryError for unknown ids
        - ProviderOperationFailure carrying the original provider cause
        - InconsistentMarketQuoteError when the two explicit results disagree on the
          requested symbol
        """
        _validate_symbol(symbol)
        _validate_timeframe(timeframe)
        self._operations.validate_candles_request(
            provider_id=market_data_provider_id,
            symbol=symbol,
            timeframe=timeframe,
            limit=candles_limit,
        )
        self._operations.validate_quote_request(
            provider_id=quote_provider_id,
            symbol=symbol,
        )

        candles_result = self._operations.fetch_candles(
            provider_id=market_data_provider_id,
            symbol=symbol,
            timeframe=timeframe,
            limit=candles_limit,
        )
        quote_result = self._operations.fetch_quote(
            provider_id=quote_provider_id,
            symbol=symbol,
        )

        expected_symbol = candles_result.symbol.strip().lower()
        actual_quote_symbol = quote_result.quote.symbol.strip().lower()
        if expected_symbol != actual_quote_symbol:
            raise InconsistentMarketQuoteError(
                symbol=symbol,
                timeframe=timeframe,
                market_data_provider_id=candles_result.provider_id,
                quote_provider_id=quote_result.provider_id,
                expected_symbol=candles_result.symbol,
                actual_quote_symbol=quote_result.quote.symbol,
            )

        return MarketQuoteResult(
            market_data_provider_id=candles_result.provider_id,
            quote_provider_id=quote_result.provider_id,
            symbol=symbol,
            timeframe=timeframe,
            candles=candles_result.candles,
            quote=quote_result.quote,
            availability=quote_result.quote.availability,
        )


def _validate_symbol(symbol: str) -> None:
    if not isinstance(symbol, str):
        raise ValueError("symbol must be a string")
    if symbol.strip() == "":
        raise ValueError("symbol must not be empty or whitespace")


def _validate_timeframe(timeframe: str) -> None:
    if not isinstance(timeframe, str):
        raise ValueError("timeframe must be a string")
    if timeframe.strip() == "":
        raise ValueError("timeframe must not be empty or whitespace")
"""Market overview application service.

Builds an immutable MarketOverview snapshot for one instrument by composing
the explicit provider operation layer (ProviderOperations) with the lab
artifact service (LabArtifactService).

Rules:
- construction and validation perform no I/O and no connect"
- nothing is fetched unless an explicit method argument requests it"
- ``None`` from source contracts means genuinely unavailable, never fabricated"
- provider/lab errors propagate as-is to the caller"
- quote and lab artifacts are optional per call; candles are always requested"
- no dependency on concrete provider implementations or the original engine"
"""

from typing import List, Optional

from src.platform.domain.market import Candle
from src.platform.domain.market_overview import MarketOverview
from src.platform.services.lab_artifacts import LabArtifactService
from src.platform.services.provider_operations import ProviderOperations


class MarketOverviewService:
    """Application service composing market data, quote,,and lab artifacts.


    The caller owns provider/source lifecycle. This service never connects,
    closes,,or silently falls back: every fetch is explicit through the injected
    operation layers.

    ``quote_provider_id`` is optional: when omitted the snapshot quote field
    remains ``None`` (unavailable rather than fabricated). The lab signal and
    trade setup are always requested when a lab service is present; the
    stability is only requested when ``strategy_name`` is provided, because the
    engine stability contract is keyed by strategy name..
    """

    def __init__(
        self,
        operations: ProviderOperations,
        lab: Optional[LabArtifactService] = None,
    ) -> None:
        if operations is None or not isinstance(operations, ProviderOperations):
            raise ValueError("operations must be a ProviderOperations")
        if lab is not None and not isinstance(lab, LabArtifactService):
            raise ValueError("lab must be a LabArtifactService when provided")
        self._operations = operations
        self._lab = lab

    def get_overview(
        self,
        symbol: str,
        timeframe: str,
        candles_provider_id: str,
        candles_limit: int = 100,
        quote_provider_id: Optional[str] = None,
        strategy_name: Optional[str] = None,
    ) -> MarketOverview:
        """Build a MarketOverview snapshot for the requested instrument.


        Parameters:
        - symbol: instrument identifier (non-empty string)
        - timeframe: timeframe string (non-empty string)
        - candles_provider_id: explicit market-data provider id (required)
        - candles_limit: maximum candles to fetch (default 100)
        - quote_provider_id: optional explicit quote provider id;; when omitted,
          the snapshot has no quote (None)
        - strategy_name: optional strategy name;; when omitted, stability is
          excluded from the snapshot (None)

        Raises: validation errors from ProviderOperations or LabArtifactService,
          provider failures,, and lab source failures propagate unchanged..
        """
        _validate_symbol(symbol)
        _validate_timeframe(timeframe)

        candles: List[Candle] = self._operations.fetch_candles(
            provider_id=candles_provider_id,
            symbol=symbol,
            timeframe=timeframe,
            limit=candles_limit,
        ).candles

        quote = None
        if quote_provider_id is not None:
            quote = self._operations.fetch_quote(
                provider_id=quote_provider_id,
                symbol=symbol,
            ).quote

        signal = None
        trade_setup = None
        stability = None
        if self._lab is not None:
            signal = self._lab.get_signal(symbol=symbol, timeframe=timeframe)
            trade_setup = self._lab.get_trade_setup(symbol=symbol, timeframe=timeframe)
            if strategy_name is not None:
                stability = self._lab.get_stability(strategy_name=strategy_name)

        availability = None
        if quote is not None:
            availability = quote.availability

        return MarketOverview(
            symbol=symbol,
            timeframe=timeframe,
            quote=quote,
            candles=candles,
            signal=signal,
            trade_setup=trade_setup,
            stability=stability,
            availability=availability,
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
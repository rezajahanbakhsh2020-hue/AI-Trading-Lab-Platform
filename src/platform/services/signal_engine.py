"""Signal engine application service.

Runs an explicitly selected external strategy over real observed market data
(candles, anda quote when requested) and honestly surfaces a validated Signal
domain object.

Rules:
- construction and validation perform no I/O and no connect;
- nothing is fetched unless an explicit ``evaluate`` call is made;
- provider/strategy selection is explicit:: no fallback,, no hidden strategy,, no auto-switch;
- ``None`` from the strategy or the provider contract means genuinely unavailable,, never fabricated;
- strategy dicts are validated before mapping into the existing Signal domain;
- validation failures raise ``ValueError`` deterministically;
- provider and strategy errors propagate unchanged to the caller;
- no dependency on concrete provider implementations or the original engine;
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.platform.domain.market import Candle
from src.platform.domain.quote import Quote
from src.platform.domain.signal import Signal
from src.platform.integrations.strategy import SignalStrategy
from src.platform.services.provider_operations import ProviderOperations


@dataclass(frozen=True)
class SignalEngineResult:
    """Signal engine outcome carrying explicitly selected provider identities."""

    symbol: str
    timeframe: str
    market_data_provider_id: str
    strategy_name: str
    signal: Optional[Signal] = None
    quote_provider_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "market_data_provider_id": self.market_data_provider_id,
            "quote_provider_id": self.quote_provider_id,
            "strategy_name": self.strategy_name,
            "signal": None if self.signal is None else self.signal.to_dict(),
        }


class SignalEngineService:
    """Application service orchestrating an explicit strategy over real data.



    The caller owns provider/strategy lifecycle. This service never connects,
    closes,, retries,, falls back,, or polls. Every fetch is explicit through the
    injected ProviderOperations layer;; the strategy is consumed only through its
    public port contract. If the strategy reports no signal (``None``) the
    result carries no signal rather than an invented one..
    """

    def __init__(self, operations: ProviderOperations, strategy: SignalStrategy) -> None:
        if operations is None or not isinstance(operations, ProviderOperations):
            raise ValueError("operations must be a ProviderOperations")
        if strategy is None or not isinstance(strategy, SignalStrategy):
            raise ValueError("strategy must be a SignalStrategy")
        self._operations = operations
        self._strategy = strategy

    def evaluate(
        self,
        symbol: str,
        timeframe: str,
        market_data_provider_id: str,
        candles_limit: int = 100,
        quote_provider_id: Optional[str] = None,
    ) -> SignalEngineResult:
        """Evaluate the explicit strategy for one market context.



        Parameters:
        - symbol: instrument identifier (non-empty string)
        - timeframe: timeframe string (non-empty string)
        - market_data_provider_id: explicit market-data provider id (required)
        - candles_limit: maximum candles to fetch (default 100)
        - quote_provider_id: optional explicit quote provider id;; when omitted,
          the strategy receives no quote (None)

        Raises:: validation errors from this service, ProviderOperations, or
        the strategy port;; provider failures,, and strategy failures propagate
        unchanged..
        """
        _validate_symbol(symbol)
        _validate_timeframe(timeframe)
        _validate_limit(candles_limit)

        candles_result = self._operations.fetch_candles(
            provider_id=market_data_provider_id,
            symbol=symbol,
            timeframe=timeframe,
            limit=candles_limit,
        )

        quote = None
        if quote_provider_id is not None:
            quote_result = self._operations.fetch_quote(
                provider_id=quote_provider_id,
                symbol=symbol,
            )
            quote = quote_result.quote

        raw = self._strategy.generate(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles_result.candles,
            quote=quote,
        )

        signal = None
        if raw is not None:
            _require_dict(raw, "signal")
            signal = Signal(
                action=_require_field(raw, "action", "signal"),
                strategy_name=_require_field(raw, "strategy_name", "signal"),
                timestamp=_require_field(raw, "timestamp", "signal"),
                confidence=raw.get("confidence"),
            )

        return SignalEngineResult(
            symbol=symbol,
            timeframe=timeframe,
            market_data_provider_id=candles_result.provider_id,
            strategy_name=_strategy_name_from(signal=signal, raw=raw),
            signal=signal,
            quote_provider_id=quote_provider_id,
        )


def _strategy_name_from(signal, raw):
    if signal is not None:
        return signal.strategy_name
    if raw is not None:
        value = raw.get("strategy_name")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "unknown"


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


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("limit must be an integer")
    if limit <= 0:
        raise ValueError("limit must be greater than zero")


def _require_dict(raw: Any, kind: str) -> None:
    if not isinstance(raw, dict):
        raise ValueError(f"{kind} strategy must return a dict, or None")


def _require_field(raw: dict, field: str, kind: str):
    if field not in raw:
        raise ValueError(f"{kind} record is missing required field '{field}'")
    return raw[field]
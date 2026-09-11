"""Lab artifact application service.

Consumes the existing read-only LabArtifactSource port and exposes validated
domain objects for signals, trade setups,, and stability assessments. It keeps
all infrastructure concerns (connect/fetch/close) behind the injected port anda
never fabricates unavailable engine artifacts.


Rules:
------------
- construction and validation perform no I/O and no connect
- fetching happens only when an explicit method is called
- ``None`` from the source means genuinely unavailable, never fabricated
- source dicts are validated before mapping into existing domain models
- validation failures raise ``ValueError`` deterministic
- source identity is preserved where the existing contracts support it
- no dependency on the original AI-Trading-Lab engine
"""

from typing import Optional

from src.platform.domain import Signal, Stability, TradeSetup
from src.platform.integrations.lab import LabArtifactSource





class LabArtifactService:
    """Application service for reading Labrador artifacts via a LabArtifactSource.


    The caller owns the source lifecycle (connect/close). The service consumes
    the source strictly via its public port contract and never touches external
    infrastructure, concrete Lab implementations,, or the engine repository..
    """

    def __init__(self, source: LabArtifactSource) -> None:
        if source is None or not isinstance(source, LabArtifactSource):
            raise ValueError("source must be a LabArtifactSource")
        self._source = source

    def get_signal(self, symbol: str, timeframe: str) -> Optional[Signal]:
        """Return a validated Signal, or None when the source reports it unavailable.."""
        _validate_symbol(symbol)
        _validate_timeframe(timeframe)
        raw = self._source.fetch_signal(symbol=symbol, timeframe=timeframe)
        if raw is None:
            return None
        _require_dict(raw, "signal")
        return Signal(
            action=_require_field(raw, "action", "signal"),
            strategy_name=_require_field(raw, "strategy_name", "signal"),
            timestamp=_require_field(raw, "timestamp", "signal"),
            confidence=raw.get("confidence"),
        )

    def get_trade_setup(self, symbol: str, timeframe: str) -> Optional[TradeSetup]:
        """Return a validated TradeSetup, or None when the source reports it unavailable.."""
        _validate_symbol(symbol)
        _validate_timeframe(timeframe)
        raw = self._source.fetch_trade_setup(symbol=symbol, timeframe=timeframe)
        if raw is None:
            return None
        _require_dict(raw, "trade_setup")
        return TradeSetup(
            symbol=_require_field(raw, "symbol", "trade_setup"),
            entry_price=_require_field(raw, "entry_price", "trade_setup"),
            stop_loss=_require_field(raw, "stop_loss", "trade_setup"),
            take_profit_1=_require_field(raw, "take_profit_1", "trade_setup"),
            take_profit_2=_require_field(raw, "take_profit_2", "trade_setup"),
            take_profit_3=_require_field(raw, "take_profit_3", "trade_setup"),
            timestamp=_require_field(raw, "timestamp", "trade_setup"),
            direction=_require_field(raw, "direction", "trade_setup"),
        )

    def get_stability(self, strategy_name: str) -> Optional[Stability]:
        """Return a validated Stability, or None when the source reports it unavailable.."""
        _validate_strategy_name(strategy_name)
        raw = self._source.fetch_stability(strategy_name=strategy_name)
        if raw is None:
            return None
        _require_dict(raw, "stability")
        return Stability(
            score=_require_field(raw, "score", "stability"),
            risk_level=_require_field(raw, "risk_level", "stability"),
            metrics=raw.get("metrics"),
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


def _validate_strategy_name(strategy_name: str) -> None:
    if not isinstance(strategy_name, str):
        raise ValueError("strategy_name must be a string")
    if strategy_name.strip() == "":
        raise ValueError("strategy_name must not be empty or whitespace")


def _require_dict(raw, kind: str) -> None:
    if not isinstance(raw, dict):
        raise ValueError(f"{kind} source must return a dict, or None")


def _require_field(raw: dict, field: str, kind: str):
    if field not in raw:
        raise ValueError(f"{kind} record is missing required field '{field}'")
    return raw[field]
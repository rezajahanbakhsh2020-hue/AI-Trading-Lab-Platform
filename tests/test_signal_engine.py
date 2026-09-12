"""Focused tests for the SignalEngineService signal engine (Part 12)."""

from typing import Any, Dict, List, Optional

import pytest

from src.platform.domain import Candle, Quote, Signal
from src.platform.integrations import SignalStrategy
from src.platform.services import (
    CandleOperationResult,
    ProviderAccess,
    ProviderOperations,
    ProviderRegistry,
    QuoteOperationResult,
    SignalEngineResult,
    SignalEngineService,
)


class FakeOperations(ProviderOperations):
    def __init__(self, candles: Optional[List[Candle]] = None, quote: Optional[Quote] = None):
        super().__init__(ProviderAccess(ProviderRegistry()))
        self.candles = candles if candles is not None else []
        self.quote = quote
        self.to_raise = None
        self.fetch_candles_calls = 0
        self.fetch_quote_calls =  0
        self.last_candles_args = None
        self.last_quote_args = None

    def fetch_candles(self, provider_id="", symbol="", timeframe="", limit=0) -> CandleOperationResult:
        if self.to_raise is not None:
            raise self.to_raise
  # noqa: E501
        self.fetch_candles_calls += 1
        self.last_candles_args = (provider_id, symbol, timeframe, limit)
        return CandleOperationResult(
            provider_id=provider_id,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            candles=self.candles,
        )

    def fetch_quote(self, provider_id="", symbol="") -> QuoteOperationResult:
  # noqa: E501
        self.fetch_quote_calls += 1
        self.last_quote_args = (provider_id, symbol)
        return QuoteOperationResult(
            provider_id=provider_id,
            symbol=symbol,
            quote=self.quote,
        )


class RecordingStrategy(SignalStrategy):
    def __init__(self, result: Any = None):
        self.result = result
        self.generate_calls =  0
        self.last_args = None

    def generate(self, symbol="", timeframe="", candles=None, quote=None):
        self.generate_calls += 1
        self.last_args = (symbol, timeframe, list(candles) if candles else [], quote)
        return self.result

    def describe(self) -> Dict[str, Any]:
        return {"name": "momentum"}


class ExplodingStrategy(SignalStrategy):
    def generate(self, symbol="", timeframe="", candles=None, quote=None):
        raise RuntimeError("strategy boom")

    def describe(self) -> Dict[str, Any]:
        return {"name": "explode"}


def _signal_dict(action: str = "buy", **overrides: Any) -> Dict[str, Any]:
    payload = {
        "action": action,
        "strategy_name": "momentum",
        "timestamp": 1700000000,
        "confidence": 0.82,
    }
    payload.update(overrides)
    return payload


def _candle_at(timestamp: Any) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=1.0,
        high=1.2,
        low=0.9,
        close=1.1,
    )


def _quote() -> Quote:
    return Quote(
        symbol="XAUUSD",
        timestamp=1700000000,
        bid=4332.0,
        ask=4332.5,
    )


def _engine(ops: Optional[FakeOperations] = None, strategy: Optional[SignalStrategy] = None):
    if ops is None:
        ops = FakeOperations()
    if strategy is None:
        strategy = RecordingStrategy()
    return SignalEngineService(operations=ops, strategy=strategy), ops, strategy


def test_requires_operations():
    with pytest.raises(ValueError):
        SignalEngineService(None, RecordingStrategy())


def test_rejects_non_operations():
    with pytest.raises(ValueError):
        SignalEngineService(object(), RecordingStrategy())  # type: ignore


def test_requires_strategy():
    with pytest.raises(ValueError):
        SignalEngineService(FakeOperations(), None)


def test_rejects_non_strategy():
    with pytest.raises(ValueError):
        SignalEngineService(FakeOperations(), object())  # type: ignore


def test_construction_does_no_io():
    ops = FakeOperations()
    strategy = RecordingStrategy(_signal_dict())
    svc, ops, strategy = _engine(ops, strategy)
    assert ops.fetch_candles_calls ==  0
    assert ops.fetch_quote_calls ==  0


def test_valid_signal_from_strategy_becomes_domain_signal():
    ops = FakeOperations(candles=[_candle_at(1)])
    strategy = RecordingStrategy(_signal_dict())
    svc, ops, strategy = _engine(ops, strategy)
    result = svc.evaluate("XAUUSD", "1h", market_data_provider_id="md_one", candles_limit=50)
    assert result.symbol ==  "XAUUSD"
    assert result.timeframe ==  "1h"
    assert result.market_data_provider_id ==  "md_one"
    assert result.strategy_name ==  "momentum"
    assert result.quote_provider_id is None
    assert isinstance(result.signal, Signal)
    assert result.signal.action == "buy"
    assert result.signal.strategy_name == "momentum"
    assert result.signal.confidence == 0.82
    assert ops.fetch_candles_calls ==  1
    assert ops.fetch_quote_calls ==  0
    assert strategy.generate_calls ==  1
    assert strategy.last_args[0] == "XAUUSD"
    assert [c.timestamp for c in strategy.last_args[2]] == [1]


def test_quote_passed_to_strategy_when_requested():
    ops = FakeOperations(candles=[_candle_at(1)], quote=_quote())
    strategy = RecordingStrategy(_signal_dict(action="sell", confidence=0.3))
    svc, ops, strategy = _engine(ops, strategy)
    result = svc.evaluate(
        "XAUUSD",
        "1h",
        market_data_provider_id="md_one",
        quote_provider_id="qt_one",
    )
    assert ops.fetch_quote_calls ==  1
    assert strategy.last_args[3] is ops.quote
    assert result.quote_provider_id ==  "qt_one"
    assert result.signal.action == "sell"
    assert result.signal.confidence ==  0.3


def test_strategy_none_means_no_signal_not_fabricated():
    strategy = RecordingStrategy(None)
    svc, _, strategy = _engine(strategy=strategy)
    result = svc.evaluate("XAUUSD", "1h", market_data_provider_id="md_one")
    assert result.signal is None
    assert result.strategy_name ==  "unknown"
    assert strategy.generate_calls ==  1


def test_empty_candles_still_reaches_strategy():
    ops = FakeOperations(candles=[])
    strategy = RecordingStrategy(_signal_dict())
    svc, _, _ = _engine(ops=ops, strategy=strategy)
    result = svc.evaluate("XAUUSD", "1h", market_data_provider_id="md_one")
    assert isinstance(result.signal, Signal)


def test_missing_required_field_raises():
    strategy = RecordingStrategy({})
    svc, _, _ = _engine(strategy=strategy)
    with pytest.raises(ValueError):
        svc.evaluate("XAUUSD", "1h", market_data_provider_id="md_one")


def test_strategy_errors_propagate():
    svc, _, _ = _engine(strategy=ExplodingStrategy())
    with pytest.raises(RuntimeError, match="strategy boom"):
        svc.evaluate("XAUUSD", "1h", market_data_provider_id="md_one")


def test_provider_failure_propagates():
    ops = FakeOperations(candles=[_candle_at(1)])
    ops.to_raise = RuntimeError("candle boom")
    svc, _, _ = _engine(ops=ops)
    with pytest.raises(RuntimeError):
        svc.evaluate("XAUUSD", "1h", market_data_provider_id="md_one")


def test_invalid_symbol_rejected_before_fetch():
    ops = FakeOperations()
    svc, ops, _ = _engine(ops=ops)
    with pytest.raises(ValueError):
        svc.evaluate(" ", "1h", market_data_provider_id="md_one")
    assert ops.fetch_candles_calls ==  0


def test_invalid_timeframe_rejected_before_fetch():
    ops = FakeOperations()
    svc, ops, _ = _engine(ops=ops)
    with pytest.raises(ValueError):
        svc.evaluate("XAUUSD", "  ", market_data_provider_id="md_one")
    assert ops.fetch_candles_calls ==  0


def test_invalid_limit_rejected_before_fetch():
    ops = FakeOperations()
    svc, ops, _ = _engine(ops=ops)
    with pytest.raises(ValueError):
        svc.evaluate("XAUUSD", "1h", market_data_provider_id="md_one", candles_limit=0)
    assert ops.fetch_candles_calls ==  0


def test_unknown_action_from_strategy_raises():
    strategy = RecordingStrategy(_signal_dict(action="moon"))
    svc, _, _ = _engine(strategy=strategy)
    with pytest.raises(ValueError):
        svc.evaluate("XAUUSD", "1h", market_data_provider_id="md_one")


def test_exported_from_services_package():
    from src.platform.services import SignalEngineService as ExportedService
    from src.platform.services import SignalEngineResult as ExportedResult
    assert ExportedService is SignalEngineService
    assert ExportedResult is SignalEngineResult


def test_strategy_port_exported():
    from src.platform.integrations import SignalStrategy as ExportedStrategy
    assert ExportedStrategy is SignalStrategy
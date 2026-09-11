"""Part 8 focused tests for the market+quote consistency boundary."""

from typing import Any, Dict, List

import pytest

from test_provider_workflow import RecordingMarketDataProvider
from test_provider_workflow import RecordingQuoteProvider
from src.platform.domain.market import Candle
from src.platform.domain.quote import Quote
from src.platform.services import (
    CATEGORY_MARKET_DATA,
    CATEGORY_QUOTE,
    InvalidOperationError,
    InconsistentMarketQuoteError,
    MarketQuoteConsistencyService,
    MarketQuoteResult,
    ProviderAccess,
    ProviderOperationFailure,
    ProviderOperations,
    ProviderRegistry,
)


def _candle(index: int) -> Dict[str, Any]:
    return {
        "timestamp": 2000 + index,
        "open": 1.0,
        "high": 1.2,
        "low": 0.9,
        "close": 1.1,
        "volume": 100.0,
    }


class SeededMarketDataProvider(RecordingMarketDataProvider):
    """Returns a fixed set of candle records when fetched."""

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        self.last_symbol = symbol
        self.last_timeframe = timeframe
        self.fetch_calls +=  1
        if self.to_raise:
            raise self.to_raise
        records: List[Dict[str, Any]] = []
        for i in range(limit):
            records.append(_candle(i))
        return records


class EmptyMarketDataProvider(SeededMarketDataProvider):
    """Market-data provider that has no candles available for the context."""

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        self.last_symbol = symbol
        self.last_timeframe = timeframe
        self.fetch_calls +=  1
        if self.to_raise:
            raise self.to_raise
        return []


class MismatchingQuoteProvider(RecordingQuoteProvider):
    """Quote provider that echoes a symbol different from the request."""

    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        self.last_symbol = symbol
        self.fetch_calls +=  1
        if self.to_raise:
            raise self.to_raise
        return {
            "symbol": "BTCUSD",
            "timestamp": 1,
            "mid": 1.0,
        }


class UnavailableQuoteProvider(RecordingQuoteProvider):
    """Quote provider returning a real quote that is explicitly unavailable."""

    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        self.last_symbol = symbol
        self.fetch_calls +=  1
        return {
            "symbol": symbol,
            "timestamp": 1,
            "mid": 1.0,
            "availability": {"status": "unavailable", "reason": "market closed"},
        }


def _build(quote_provider=None, market_data_provider=None):
    registry = ProviderRegistry()
    md = market_data_provider if market_data_provider is not None else SeededMarketDataProvider("md_one")
    qt = quote_provider if quote_provider is not None else RecordingQuoteProvider("qt_one")
    registry.register("md_one", CATEGORY_MARKET_DATA, md)
    registry.register("qt_one", CATEGORY_QUOTE, qt)
    access = ProviderAccess(registry)
    operations = ProviderOperations(access)
    service = MarketQuoteConsistencyService(operations)
    return service, operations, md, qt


def test_requires_operations():
    with pytest.raises(ValueError):
        MarketQuoteConsistencyService(None)


def test_valid_resolution_preserves_both_identities():
    service, _, md, qt = _build()
    result = service.resolve("XAUUSD", "1h", "md_one", "qt_one", candles_limit=2)
    assert isinstance(result, MarketQuoteResult)
    assert result.market_data_provider_id == "md_one"
    assert result.quote_provider_id == "qt_one"
    assert result.symbol == "XAUUSD"
    assert result.timeframe == "1h"
    assert len(result.candles) ==  2
    assert all(isinstance(c, Candle) for c in result.candles)
    assert isinstance(result.quote, Quote)
    assert md.fetch_calls ==  1
    assert qt.fetch_calls ==  1


def test_market_data_identity_preserved():
    service, _, _, _ = _build()
    result = service.resolve("XAUUSD", "1h", "md_one", "qt_one")
    assert result.market_data_provider_id == "md_one"


def test_quote_identity_preserved():
    service, _, _, _ = _build()
    result = service.resolve("XAUUSD", "1h", "md_one", "qt_one")
    assert result.quote_provider_id == "qt_one"


def test_identities_remain_separate_in_result():
    service, _, _, _ = _build()
    result = service.resolve("XAUUSD", "1h", "md_one", "qt_one")
    assert result.market_data_provider_id != result.quote_provider_id
    d = result.to_dict()
    assert d["market_data_provider_id"] == "md_one"
    assert d["quote_provider_id"] == "qt_one"


def test_only_selected_providers_are_called():
    service, _, md, qt = _build()
    service.resolve("XAUUSD", "1h", "md_one", "qt_one", candles_limit=3)
    assert md.fetch_calls ==  1
    assert qt.fetch_calls ==   1
    assert md.last_symbol == "XAUUSD"
    assert md.last_timeframe == "1h"
    assert qt.last_symbol == "XAUUSD"


def test_resolution_does_not_connect_or_close():
    service, _, md, qt = _build()
    service.resolve("XAUUSD", "1h", "md_one", "qt_one")
    assert md.connect_calls ==   0
    assert md.close_calls ==   0
    assert qt.connect_calls ==   0
    assert qt.close_calls ==   0


def test_inconsistent_symbols_fail_clearly():
    service, _, _, _ = _build(quote_provider=MismatchingQuoteProvider("qt_one"))
    with pytest.raises(InconsistentMarketQuoteError) as exc:
        service.resolve("XAUUSD", "1h", "md_one", "qt_one")
    captured = exc.value
    assert captured.expected_symbol == "XAUUSD"
    assert captured.actual_quote_symbol == "BTCUSD"
    assert captured.market_data_provider_id == "md_one"
    assert captured.quote_provider_id == "qt_one"
    assert captured.symbol == "XAUUSD"
    assert captured.timeframe == "1h"


def test_inconsistent_failure_is_not_a_successful_result():
    service, _, _, _ = _build(quote_provider=MismatchingQuoteProvider("qt_one"))
    with pytest.raises(InconsistentMarketQuoteError):
        service.resolve("XAUUSD", "1h", "md_one", "qt_one")


def test_market_data_failure_propagates_without_fallback():
    service, _, md, qt = _build()
    md.to_raise = RuntimeError("candle fetch exploded")
    with pytest.raises(ProviderOperationFailure) as exc:
        service.resolve("XAUUSD", "1h", "md_one", "qt_one")
    assert isinstance(exc.value.cause, RuntimeError)
    assert str(exc.value.cause) == "candle fetch exploded"
    assert qt.fetch_calls == 0


def test_quote_failure_propagates_without_fallback():
    service, _, md, qt = _build()
    qt.to_raise = RuntimeError("quote fetch exploded")
    with pytest.raises(ProviderOperationFailure) as exc:
        service.resolve("XAUUSD", "1h", "md_one", "qt_one")
    assert isinstance(exc.value.cause, RuntimeError)
    assert str(exc.value.cause) == "quote fetch exploded"
    assert md.fetch_calls == 1


def test_unavailable_quote_is_preserved_not_fabricated():
    service, _, _, _ = _build(quote_provider=UnavailableQuoteProvider("qt_one"))
    result = service.resolve("XAUUSD", "1h", "md_one", "qt_one")
    assert result.quote.availability is not None
    assert result.quote.availability.status == "unavailable"
    assert result.availability.status == "unavailable"
    assert result.quote.mid == 1.0
    assert result.to_dict()["quote"]["availability"]["status"] == "unavailable"


def test_unavailable_market_data_is_preserved():
    service, _, _, _ = _build(market_data_provider=EmptyMarketDataProvider("md_one"))
    result = service.resolve("XAUUSD", "1h", "md_one", "qt_one")
    assert result.candles == []


def test_no_fabricated_quote_from_market_data():
    service, _, md, qt = _build()
    result = service.resolve("XAUUSD", "1h", "md_one", "qt_one")
    assert len(result.candles) == 100
    assert result.quote is not None
    assert qt.fetch_calls == 1


def test_no_fabricated_market_data_from_quote():
    service, _, _, qt = _build(quote_provider=UnavailableQuoteProvider("qt_one"))
    result = service.resolve("XAUUSD", "1h", "md_one", "qt_one")
    assert result.to_dict()["quote"]["mid"] == 1.0


def test_invalid_input_rejected_before_io():
    service, _, md, qt = _build()
    with pytest.raises(ValueError):
        service.resolve("", "1h", "md_one", "qt_one")
    with pytest.raises(ValueError):
        service.resolve("XAUUSD", "", "md_one", "qt_one")
    with pytest.raises(InvalidOperationError):
        service.resolve("XAUUSD", "1h", "", "qt_one")
    with pytest.raises(InvalidOperationError):
        service.resolve("XAUUSD", "1h", "md_one", "")
    with pytest.raises(InvalidOperationError):
        service.resolve("XAUUSD", "1h", "md_one", "qt_one", candles_limit=0)
    assert md.fetch_calls == 0
    assert qt.fetch_calls == 0


def test_to_dict_follows_contract_shape():
    service, _, _, _ = _build()
    result = service.resolve("XAUUSD", "1h", "md_one", "qt_one", candles_limit=1)
    d = result.to_dict()
    assert set(d.keys()) == {
        "market_data_provider_id",
        "quote_provider_id",
        "symbol",
        "timeframe",
        "candles",
        "quote",
        "availability",
    }
    assert d["market_data_provider_id"] == "md_one"
    assert d["quote_provider_id"] == "qt_one"
    assert d["symbol"] == "XAUUSD"
    assert d["timeframe"] == "1h"
    assert isinstance(d["candles"], list) and len(d["candles"]) ==  1
    assert d["quote"] is not None
    assert d["availability"] is None
"""Part 5 focused tests for the application provider operation layer."""
from typing import Any, Dict, List

import pytest

from test_provider_access import FakeMarketDataProvider
from test_provider_access import FakeQuoteProvider
from test_provider_workflow import RecordingMarketDataProvider
from test_provider_workflow import RecordingQuoteProvider
from src.platform.adapters.provider_adapter import ProviderAdapter
from src.platform.adapters.quote_adapter import QuoteAdapter
from src.platform.domain.market import Candle
from src.platform.domain.quote import Quote
from src.platform.services import CATEGORY_MARKET_DATA
from src.platform.services import CATEGORY_QUOTE
from src.platform.services import CandleOperationResult
from src.platform.services import InvalidOperationError
from src.platform.services import MarketDataService
from src.platform.services import ProviderAccess
from src.platform.services import ProviderOperationFailure
from src.platform.services import ProviderOperations
from src.platform.services import ProviderRegistry
from src.platform.services import QuoteOperationResult
from src.platform.services import QuoteService
from src.platform.services import UnknownProviderCategoryError
from src.platform.services import UnknownProviderError


def _candle(index: int) -> Dict[str, Any]:
    return {
        "timestamp": 1000 + index,
        "open": 1.0,
        "high": 1.2,
        "low": 0.9,
        "close": 1.1,
        "volume": 100.0,
    }


class SeededMarketDataProvider(RecordingMarketDataProvider):
    """Returns a fixed number of candle records when fetched."""

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        self.last_symbol = symbol
        self.last_timeframe = timeframe
        self.fetch_calls += 1
        records: List[Dict[str, Any]] = []
        for i in range(limit):
            records.append(_candle(i))
        return records


def _build_ops():
    registry = ProviderRegistry()
    md = RecordingMarketDataProvider("md_one")
    qt = RecordingQuoteProvider("qt_one")
    registry.register("md_one", CATEGORY_MARKET_DATA, md)
    registry.register("qt_one", CATEGORY_QUOTE, qt)
    access = ProviderAccess(registry)
    ops = ProviderOperations(access)
    return ops, md, qt


def test_requires_access():
    with pytest.raises(ValueError):
        ProviderOperations(None)


def test_fetch_candles_explicit_operation():
    registry = ProviderRegistry()
    md = SeededMarketDataProvider("md_one")
    registry.register("md_one", CATEGORY_MARKET_DATA, md)
    ops = ProviderOperations(ProviderAccess(registry))
    result = ops.fetch_candles("md_one", "XAUUSD", "1h", 3)
    assert isinstance(result, CandleOperationResult)
    assert result.provider_id == "md_one"
    assert result.symbol == "XAUUSD"
    assert result.timeframe == "1h"
    assert result.limit == 3
    assert len(result.candles) == 3
    assert isinstance(result.candles[0], Candle)


def test_fetch_candles_empty_result():
    ops, _, _ = _build_ops()
    result = ops.fetch_candles("md_one", "XAUUSD", "1h", 3)
    assert result.candles == []


def test_fetch_quote_explicit_operation():
    ops, _, _ = _build_ops()
    result = ops.fetch_quote("qt_one", "XAUUSD")
    assert isinstance(result, QuoteOperationResult)
    assert result.provider_id == "qt_one"
    assert result.symbol == "XAUUSD"
    assert isinstance(result.quote, Quote)


def test_validation_rejects_bad_requests():
    ops, _, _ = _build_ops()
    with pytest.raises(InvalidOperationError):
        ops.validate_candles_request("", "XAUUSD", "1h",  3)
    with pytest.raises(InvalidOperationError):
        ops.validate_candles_request("md_one", " ", "1h",  3)
    with pytest.raises(InvalidOperationError):
        ops.validate_candles_request("md_one", "XAUUSD", "  ",  3)
    with pytest.raises(InvalidOperationError):
        ops.validate_candles_request("md_one", "XAUUSD", "1h",  0)
    with pytest.raises(InvalidOperationError):
        ops.fetch_candles("md_one", "XAUUSD", "1h",  -1)
    with pytest.raises(InvalidOperationError):
        ops.validate_quote_request("", "XAUUSD")
    with pytest.raises(InvalidOperationError):
        ops.validate_quote_request("qt_one", "  ")
    with pytest.raises(InvalidOperationError):
        ops.fetch_quote("qt_one", "")


def test_unknown_provider_fails():
    ops, _, _ = _build_ops()
    with pytest.raises(UnknownProviderError, match="nope"):
        ops.fetch_candles("nope", "XAUUSD", "1h",  1)
    with pytest.raises(UnknownProviderError, match="nope"):
        ops.fetch_quote("nope", "XAUUSD")


def test_unknown_category_fails():
    ops, _, _ = _build_ops()
    with pytest.raises(UnknownProviderCategoryError, match="news"):
        ops._access.resolve_provider("news", "wire")


def test_provider_failure_preserves_identity_and_cause():
    ops, md, qt = _build_ops()
    md.to_raise = RuntimeError("candle boom")
    with pytest.raises(ProviderOperationFailure) as caught:
        ops.fetch_candles("md_one", "XAUUSD", "1h",  1)
    assert caught.value.provider_id == "md_one"
    assert caught.value.category == "market_data"
    assert caught.value.operation == "fetch_candles"
    assert isinstance(caught.value.cause, RuntimeError)
    assert "candle boom" in str(caught.value)


    qt.to_raise = RuntimeError("quote boom")
    with pytest.raises(ProviderOperationFailure) as caught:
        ops.fetch_quote("qt_one", "XAUUSD")
    assert caught.value.provider_id == "qt_one"
    assert caught.value.category == "quote"
    assert caught.value.operation == "fetch_quote"
    assert isinstance(caught.value.cause, RuntimeError)


def test_failure_does_not_fall_back():
    ops, md, qt = _build_ops()
    md.to_raise = RuntimeError("boom")
    with pytest.raises(ProviderOperationFailure):
        ops.fetch_candles("md_one", "XAUUSD", "1h",  1)
    assert qt.fetch_calls == 0
    assert qt.connect_calls == 0


    qt.to_raise = RuntimeError("boom")
    with pytest.raises(ProviderOperationFailure):
        ops.fetch_quote("qt_one", "XAUUSD")
    assert md.fetch_calls ==  1
    assert md.connect_calls == 0


def test_construction_and_validation_no_io():
    ops, md, qt = _build_ops()
    ops.validate_candles_request("md_one", "XAUUSD", "1h",  3)
    ops.validate_quote_request("qt_one", "XAUUSD")
    assert md.connect_calls == 0
    assert md.fetch_calls ==  0
    assert md.close_calls == 0
    assert qt.connect_calls == 0
    assert qt.fetch_calls ==  0
    assert qt.close_calls == 0


def test_explicit_fetch_only_activates_chosen_provider():
    ops, md, qt = _build_ops()
    ops.fetch_candles("md_one", "XAUUSD", "1h",  1)
    assert md.fetch_calls == 1
    assert qt.fetch_calls == 0
    assert qt.connect_calls == 0
    assert md.connect_calls == 0


def test_compatible_with_existing_services():
    registry = ProviderRegistry()
    md = SeededMarketDataProvider("md_one")
    qt = RecordingQuoteProvider("qt_one")
    registry.register("md_one", CATEGORY_MARKET_DATA, md)
    registry.register("qt_one", CATEGORY_QUOTE, qt)

    ops = ProviderOperations(ProviderAccess(registry))
    candle_result = ops.fetch_candles("md_one", "XAUUSD", "1h",  2)
    md_service = MarketDataService(ProviderAdapter(md))
    direct_candles = md_service.get_candles("XAUUSD", "1h",  2)
    assert candle_result.candles == direct_candles
    candle_result.candles[0].close == 1.1
    assert candle_result.candles[0].close == 1.1


    quote_result = ops.fetch_quote("qt_one", "XAUUSD")
    qt_service = QuoteService(QuoteAdapter(qt))
    direct_quote = qt_service.get_quote("XAUUSD")
    assert quote_result.quote == direct_quote
"""Part 4 focused tests for provider-based application workflow."""
from typing import Any, Dict, List

import pytest

from test_provider_access import FakeMarketDataProvider, FakeQuoteProvider
from src.platform.domain.market import Candle
from src.platform.domain.quote import Quote
from src.platform.providers.biquote import BiQuoteProvider
from src.platform.providers.biquote_quote import BiQuoteQuoteProvider
from src.platform.services import (
    CATEGORY_MARKET_DATA,
    CATEGORY_QUOTE,
    CandleResult,
    MarketDataHandle,
    ProviderAccess,
    ProviderRegistry,
    ProviderWorkflow,
    QuoteHandle,
    QuoteResult,
    UnknownProviderCategoryError,
    UnknownProviderError,
)


class RecordingMarketDataProvider(FakeMarketDataProvider):
    """Tracks the exact fetch args atop the base counting fake."""

    def __init__(self, name: str = "md_rec"):
        super().__init__(name=name)
        self.last_symbol = None
        self.last_timeframe = None
        self.to_raise = None

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        self.last_symbol = symbol
        self.last_timeframe = timeframe
        self.fetch_calls +=  1
        if self.to_raise:
            raise self.to_raise
        return []


class RecordingQuoteProvider(FakeQuoteProvider):
    """Tracks the exact fetched symbol atop the base counting fake."""

    def __init__(self, name: str = "qt_rec"):
        super().__init__(name=name)
        self.last_symbol = None
        self.to_raise = None

    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        self.last_symbol = symbol
        self.fetch_calls +=  1
        if self.to_raise:
            raise self.to_raise
        return {"symbol": symbol, "timestamp": 1, "mid": 1.0}


def _build_workflow():
    registry = ProviderRegistry()
    md = RecordingMarketDataProvider("md_one")
    qt = RecordingQuoteProvider("qt_one")
    registry.register("md_one", CATEGORY_MARKET_DATA, md)
    registry.register("qt_one", CATEGORY_QUOTE, qt)
    access = ProviderAccess(registry)
    workflow = ProviderWorkflow(access)
    return workflow, md, qt


def test_workflow_requires_access():
    with pytest.raises(ValueError):
        ProviderWorkflow(None)


def test_explicit_market_data_handle_identity():
    workflow, md, _ = _build_workflow()
    handle = workflow.market_data("md_one")
    assert isinstance(handle, MarketDataHandle)
    assert handle.provider_id == "md_one"
    assert handle.provider is md


def test_explicit_quote_handle_identity():
    workflow, _, qt = _build_workflow()
    handle = workflow.quote("qt_one")
    assert isinstance(handle, QuoteHandle)
    assert handle.provider_id == "qt_one"
    assert handle.provider is qt


def test_construction_and_resolution_no_activation():
    workflow, md, qt = _build_workflow()
    workflow.market_data("md_one")
    workflow.quote("qt_one")
    assert md.connect_calls ==  0
    assert md.fetch_calls ==  0
    assert md.close_calls ==  0
    assert qt.connect_calls ==  0
    assert qt.fetch_calls ==  0
    assert qt.close_calls ==  0


def test_get_candles_invokes_selected_provider():
    workflow, md, _ = _build_workflow()
    result = workflow.get_candles("md_one", "XAUUSD", "1h", 5)
    assert isinstance(result, CandleResult)
    assert result.provider_id == "md_one"
    assert md.fetch_calls ==  1
    assert md.last_symbol == "XAUUSD"
    assert md.last_timeframe == "1h"


def test_get_quote_invokes_selected_provider():
    workflow, _, qt = _build_workflow()
    result = workflow.get_quote("qt_one", "XAUUSD")
    assert isinstance(result, QuoteResult)
    assert result.provider_id == "qt_one"
    assert qt.fetch_calls ==  1
    assert qt.last_symbol == "XAUUSD"


def test_unknown_provider_fails_in_workflow():
    workflow, _, _ = _build_workflow()
    with pytest.raises(UnknownProviderError):
        workflow.get_candles("nope", "XAUUSD", "1h", 1)
    with pytest.raises(UnknownProviderError):
        workflow.get_quote("nope", "XAUUSD")


def test_unknown_category_fails_in_workflow():
    workflow, _, _ = _build_workflow()
    with pytest.raises(UnknownProviderCategoryError, match="news"):
        workflow.resolve_provider("news", "wire")

def test_provider_failure_propagates_without_fallback():
    workflow, md, qt = _build_workflow()
    md.to_raise = RuntimeError("candle fetch exploded")
    with pytest.raises(RuntimeError, match="candle fetch exploded"):
        workflow.get_candles("md_one", "XAUUSD", "1h", 1)
    assert qt.fetch_calls ==  0
    assert qt.connect_calls ==  0


def test_quote_failure_propagates_without_fallback():
    workflow, md, qt = _build_workflow()
    qt.to_raise = RuntimeError("quote fetch exploded")
    with pytest.raises(RuntimeError, match="quote fetch exploded"):
        workflow.get_quote("qt_one", "XAUUSD")
    assert md.fetch_calls ==  0
    assert md.connect_calls ==  0


def test_explicit_fetch_only_activates_chosen_provider():
    workflow, md, qt = _build_workflow()
    workflow.get_candles("md_one", "XAUUSD", "1h", 1)
    assert md.fetch_calls ==  1
    assert qt.fetch_calls ==  0
    assert qt.connect_calls ==  0
    assert md.connect_calls ==  0
    assert md.close_calls ==  0
    assert qt.close_calls ==  0


def test_biquote_providers_work_through_workflow():
    registry = ProviderRegistry()
    md = BiQuoteProvider()
    qt = BiQuoteQuoteProvider()
    registry.register("biquote", CATEGORY_MARKET_DATA, md)
    registry.register("biquote_quote", CATEGORY_QUOTE, qt)
    workflow = ProviderWorkflow(ProviderAccess(registry))
    md_handle = workflow.market_data("biquote")
    qt_handle = workflow.quote("biquote_quote")
    assert isinstance(md_handle.provider, BiQuoteProvider)
    assert isinstance(qt_handle.provider, BiQuoteQuoteProvider)
    assert md_handle.provider_id == "biquote"
    assert qt_handle.provider_id == "biquote_quote"
    # No network/I/O happens just from constructing the workflow.

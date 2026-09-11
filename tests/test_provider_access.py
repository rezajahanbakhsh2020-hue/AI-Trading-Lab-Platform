
"""Part 3 focused tests for application provider access layer."""
from typing import Any, Dict, List
import pytest
from src.platform.adapters.provider_adapter import ProviderAdapter
from src.platform.adapters.quote_adapter import QuoteAdapter
from src.platform.domain.quote import Quote
from src.platform.domain.market import Candle
from src.platform.providers.biquote import BiQuoteProvider
from src.platform.providers.biquote_quote import BiQuoteQuoteProvider
from src.platform.services import (
    CATEGORY_MARKET_DATA,
    CATEGORY_QUOTE,
    DuplicateProviderError,
    MarketDataService,
    ProviderAccess,
    ProviderRegistry,
    QuoteService,
    UnknownProviderCategoryError,
    UnknownProviderError,
)
from src.platform.providers import MarketDataProvider, QuoteProvider


class FakeMarketDataProvider(MarketDataProvider):
    def __init__(self, name: str = "FakeMarketDataProvider"):
        self.name = name
        self.connect_calls = 0
        self.close_calls = 0
        self.fetch_calls = 0
        self.describe_calls = 0

    def connect(self) -> None:
        self.connect_calls += 1

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        self.fetch_calls += 1
        return []

    def close(self) -> None:
        self.close_calls += 1

    def describe(self) -> Dict[str, Any]:
        self.describe_calls += 1
        return {"name": self.name, "kind": "market_data"}


class FakeQuoteProvider(QuoteProvider):
    def __init__(self, name: str = "FakeQuoteProvider"):
        self.name = name
        self.connect_calls = 0
        self.close_calls = 0
        self.fetch_calls = 0
        self.describe_calls = 0

    def connect(self) -> None:
        self.connect_calls += 1

    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        self.fetch_calls += 1
        return {"symbol": symbol, "timestamp": 1, "mid": 1.0}

    def close(self) -> None:
        self.close_calls += 1

    def describe(self) -> Dict[str, Any]:
        self.describe_calls += 1
        return {"name": self.name, "kind": "quote"}



def _build_access():
    registry = ProviderRegistry()
    md = FakeMarketDataProvider("md_one")
    qt = FakeQuoteProvider("qt_one")
    registry.register("md_one", CATEGORY_MARKET_DATA, md)
    registry.register("qt_one", CATEGORY_QUOTE, qt)
    return ProviderAccess(registry), md, qt


def test_access_composes_registry_and_resolver():
    access, _, _ = _build_access()
    assert isinstance(access, ProviderAccess)
    assert access.supported_categories() == ("market_data", "quote")


def test_explicit_market_data_resolution():
    access, md, _ = _build_access()
    assert access.market_data_provider("md_one") is md


def test_explicit_quote_resolution():
    access, _, qt = _build_access()
    assert access.quote_provider("qt_one") is qt


def test_resolve_provider_generic():
    access, md, qt = _build_access()
    assert access.resolve_provider(CATEGORY_MARKET_DATA, "md_one")is md
    assert access.resolve_provider(CATEGORY_QUOTE, "qt_one")is qt


def test_unknown_provider_fails_without_fallback():
    access, _, _ = _build_access()
    with pytest.raises(UnknownProviderError,
        match="nonexistent"):
        access.market_data_provider("nonexistent")
    with pytest.raises(UnknownProviderError,
        match="nonexistent"):
        access.quote_provider("nonexistent")


def test_missing_category_provider_fails():
    access, _, _ = _build_access()
    with pytest.raises(UnknownProviderError):
        access.market_data_provider("qt_one")


def test_unknown_category_fails():
    access, _, _ = _build_access()
    with pytest.raises(UnknownProviderCategoryError,
        match="news"):
        access.resolve_provider("news", "wire")


def test_no_implicit_fallback():
    registry = ProviderRegistry()
    access = ProviderAccess(registry)
    with pytest.raises(UnknownProviderError):
        access.market_data_provider("md_one")
    assert access.list_providers() == ()


def test_registration_failure_isolation():
    registry = ProviderRegistry()
    registry.register("md", CATEGORY_MARKET_DATA,
        FakeMarketDataProvider())
    with pytest.raises(DuplicateProviderError):
        registry.register("md", CATEGORY_MARKET_DATA,
            FakeMarketDataProvider())
    with pytest.raises(UnknownProviderCategoryError):
        registry.register("wire", "news", object())


def test_resolution_never_activates_providers():
    access, md, qt = _build_access()
    access.market_data_provider("md_one")
    access.quote_provider("qt_one")
    access.list_providers()
    access.supported_categories()
    assert md.connect_calls == 0
    assert md.fetch_calls == 0
    assert md.close_calls == 0
    assert qt.connect_calls == 0
    assert qt.fetch_calls == 0
    assert qt.close_calls == 0


def test_existing_market_data_service_compatible():
    access, _, _ = _build_access()
    provider = access.market_data_provider("md_one")
    service = MarketDataService(ProviderAdapter(provider))
    candles = service.get_candles("XAUUSD", "1h", 5)
    assert candles == [] and isinstance(candles, list)


def test_existing_quote_service_compatible():
    access, _, _ = _build_access()
    provider = access.quote_provider("qt_one")
    service = QuoteService(QuoteAdapter(provider))
    quote = service.get_quote("XAUUSD")
    assert isinstance(quote, Quote)
    assert quote.mid == 1.0


def test_biquote_accessible_through_access_layer():
    registry = ProviderRegistry()
    md = BiQuoteProvider()
    qt = BiQuoteQuoteProvider()
    registry.register("biquote", CATEGORY_MARKET_DATA, md)
    registry.register("biquote_quote", CATEGORY_QUOTE, qt)
    access = ProviderAccess(registry)
    assert isinstance(access.market_data_provider("biquote"), BiQuoteProvider)
    assert isinstance(access.quote_provider("biquote_quote"),
        BiQuoteQuoteProvider)


def test_domain_and_integration_boundaries_remain_intact():
    import src.platform.domain.market as market_module
    import src.platform.integrations.lab as lab_module
    assert "ProviderRegistry" not in dir(market_module)
    assert "ProviderRegistry" not in dir(lab_module)
    assert "ProviderAccess" not in dir(market_module)
    assert "ProviderWorkflow" not in dir(market_module)

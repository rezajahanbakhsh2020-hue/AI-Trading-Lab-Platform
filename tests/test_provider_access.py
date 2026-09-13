
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
    InvalidProviderRegistrationError,
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


def test_access_requires_registry():
    with pytest.raises(ValueError, match="ProviderRegistry"):
        ProviderAccess(None)
    with pytest.raises(ValueError, match="ProviderRegistry"):
        ProviderAccess(object())


def test_access_is_not_a_singleton():
    first_registry = ProviderRegistry()
    second_registry = ProviderRegistry()
    first = ProviderAccess(first_registry)
    second = ProviderAccess(second_registry)
    first_registry.register("md_one", CATEGORY_MARKET_DATA, FakeMarketDataProvider())
    assert first.market_data_provider("md_one") is not None
    with pytest.raises(UnknownProviderError):
        second.market_data_provider("md_one")
    assert first is not second


def test_repeated_resolution_is_deterministic():
    access, md, qt = _build_access()
    assert access.market_data_provider("md_one") is md
    assert access.market_data_provider("md_one") is md
    assert access.quote_provider("qt_one") is qt
    assert access.quote_provider("qt_one") is qt
    assert access.resolve_provider(CATEGORY_MARKET_DATA, "md_one") is md
    assert access.resolve_provider(CATEGORY_QUOTE, "qt_one") is qt


def test_no_automatic_provider_switching():
    registry = ProviderRegistry()
    first = FakeMarketDataProvider("first")
    second = FakeMarketDataProvider("second")
    registry.register("first", CATEGORY_MARKET_DATA, first)
    registry.register("second", CATEGORY_MARKET_DATA, second)
    access = ProviderAccess(registry)
    assert access.market_data_provider("first") is first
    assert access.market_data_provider("second") is second
    assert access.market_data_provider("first") is not second
    with pytest.raises(UnknownProviderError):
        access.market_data_provider("third")


def test_contains_is_explicit_and_does_not_fallback():
    access, _, _ = _build_access()
    assert access.contains(CATEGORY_MARKET_DATA, "md_one") is True
    assert access.contains(CATEGORY_QUOTE, "qt_one") is True
    assert access.contains(CATEGORY_MARKET_DATA, "qt_one") is False
    assert access.contains(CATEGORY_QUOTE, "md_one") is False
    assert access.contains(CATEGORY_MARKET_DATA, "nonexistent") is False


def test_contains_unknown_category_fails():
    access, _, _ = _build_access()
    with pytest.raises(UnknownProviderCategoryError, match="news"):
        access.contains("news", "wire")


def test_invalid_provider_id_propagates_existing_error():
    access, _, _ = _build_access()
    with pytest.raises(InvalidProviderRegistrationError):
        access.market_data_provider("bi-quote")
    with pytest.raises(InvalidProviderRegistrationError):
        access.quote_provider("")
    with pytest.raises(InvalidProviderRegistrationError):
        access.resolve_provider(CATEGORY_MARKET_DATA, "   ")


def test_resolution_does_not_call_describe_or_lifecycle():
    access, md, qt = _build_access()
    describe_md = md.describe_calls
    describe_qt = qt.describe_calls
    access.market_data_provider("md_one")
    access.quote_provider("qt_one")
    access.resolve_provider(CATEGORY_MARKET_DATA, "md_one")
    access.contains(CATEGORY_MARKET_DATA, "md_one")
    access.list_providers()
    access.supported_categories()
    assert md.describe_calls == describe_md
    assert qt.describe_calls == describe_qt
    assert md.connect_calls == 0
    assert md.fetch_calls == 0
    assert md.close_calls == 0
    assert qt.connect_calls == 0
    assert qt.fetch_calls == 0
    assert qt.close_calls == 0


def test_list_providers_is_sorted_and_does_not_activate():
    registry = ProviderRegistry()
    zeta = FakeQuoteProvider("zeta")
    alpha = FakeMarketDataProvider("alpha")
    mid = FakeMarketDataProvider("mid")
    registry.register("zeta", CATEGORY_QUOTE, zeta)
    registry.register("alpha", CATEGORY_MARKET_DATA, alpha)
    registry.register("mid", CATEGORY_MARKET_DATA, mid)
    access = ProviderAccess(registry)
    listed = access.list_providers()
    assert [(item.category, item.provider_id) for item in listed] == [
        ("market_data", "alpha"),
        ("market_data", "mid"),
        ("quote", "zeta"),
    ]
    assert [item.provider_id for item in access.list_providers(CATEGORY_QUOTE)] == ["zeta"]
    assert alpha.connect_calls == 0
    assert zeta.fetch_calls == 0


def test_same_id_in_different_categories_stays_explicit():
    registry = ProviderRegistry()
    candles = FakeMarketDataProvider("shared")
    quotes = FakeQuoteProvider("shared")
    registry.register("shared", CATEGORY_MARKET_DATA, candles)
    registry.register("shared", CATEGORY_QUOTE, quotes)
    access = ProviderAccess(registry)
    assert access.market_data_provider("shared") is candles
    assert access.quote_provider("shared") is quotes
    assert access.market_data_provider("shared") is not quotes


def test_get_record_preserves_explicit_identity():
    access, md, qt = _build_access()
    record = access.get_record(CATEGORY_MARKET_DATA, "md_one")
    assert record.provider_id == "md_one"
    assert record.category == "market_data"
    assert record.provider is md
    quote_record = access.get_record(CATEGORY_QUOTE, "qt_one")
    assert quote_record.provider_id == "qt_one"
    assert quote_record.category == "quote"
    assert quote_record.provider is qt


def test_get_record_unknown_provider_fails_without_fallback():
    access, _, _ = _build_access()
    with pytest.raises(UnknownProviderError, match="nonexistent"):
        access.get_record(CATEGORY_MARKET_DATA, "nonexistent")
    with pytest.raises(UnknownProviderError):
        access.get_record(CATEGORY_MARKET_DATA, "qt_one")
    with pytest.raises(UnknownProviderCategoryError, match="news"):
        access.get_record("news", "wire")


def test_get_record_repeated_resolution_is_deterministic():
    access, md, _ = _build_access()
    first = access.get_record(CATEGORY_MARKET_DATA, "md_one")
    second = access.get_record(CATEGORY_MARKET_DATA, "md_one")
    assert first.provider is md
    assert second.provider is md
    assert first.provider is second.provider
    assert first.provider_id == second.provider_id
    assert first.category == second.category


def test_get_record_does_not_activate_providers():
    access, md, qt = _build_access()
    access.get_record(CATEGORY_MARKET_DATA, "md_one")
    access.get_record(CATEGORY_QUOTE, "qt_one")
    assert md.connect_calls == 0
    assert md.fetch_calls == 0
    assert md.close_calls == 0
    assert qt.connect_calls == 0
    assert qt.fetch_calls == 0
    assert qt.close_calls == 0


def test_resolver_errors_propagate_through_access():
    access, _, _ = _build_access()
    with pytest.raises(InvalidProviderRegistrationError):
        access.get_record(CATEGORY_MARKET_DATA, "1bad")
    with pytest.raises(UnknownProviderCategoryError):
        access.list_providers("news")


def test_extra_category_resolves_through_access_without_fallback():
    class NewsProvider:
        def describe(self):
            return {"name": "wire"}

    news = NewsProvider()
    registry = ProviderRegistry(extra_categories={"news": NewsProvider})
    registry.register("wire", "news", news)
    access = ProviderAccess(registry)
    assert access.resolve_provider("news", "wire") is news
    record = access.get_record("news", "wire")
    assert record.provider is news
    assert record.category == "news"
    assert record.provider_id == "wire"
    with pytest.raises(UnknownProviderError):
        access.resolve_provider("news", "missing")
    with pytest.raises(UnknownProviderError):
        access.market_data_provider("wire")


def test_access_module_does_not_import_concrete_providers():
    import src.platform.services.provider_access as access_module

    assert "BiQuoteProvider" not in dir(access_module)
    assert "BiQuoteQuoteProvider" not in dir(access_module)

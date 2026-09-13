from typing import Any, Dict, List

import pytest

from src.platform.providers import MarketDataProvider, QuoteProvider
from src.platform.services import (
    CATEGORY_MARKET_DATA,
    CATEGORY_QUOTE,
    DuplicateProviderError,
    InvalidProviderRegistrationError,
    ProviderRegistry,
    ProviderResolver,
    UnknownProviderCategoryError,
    UnknownProviderError,
)


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


class FakeNewsPort:
    def describe(self) -> Dict[str, Any]:
        return {"name": "FakeNews"}


def test_registry_starts_empty_and_is_not_a_singleton():
    first = ProviderRegistry()
    second = ProviderRegistry()
    first.register("biquote", CATEGORY_MARKET_DATA, FakeMarketDataProvider())
    assert first.list_providers()
    assert second.list_providers() == ()
    assert first is not second


def test_supported_categories_are_sorted_and_stable():
    registry = ProviderRegistry()
    assert registry.supported_categories() == ("market_data", "quote")


def test_register_and_resolve_market_data_and_quote():
    registry = ProviderRegistry()
    candles = FakeMarketDataProvider("candles")
    quotes = FakeQuoteProvider("quotes")
    registry.register("biquote", "market_data", candles)
    registry.register("biquote_quote", "quote", quotes)
    resolver = ProviderResolver(registry)
    assert resolver.resolve_market_data("biquote") is candles
    assert resolver.resolve_quote("biquote_quote") is quotes
    assert resolver.resolve("MARKET_DATA", "BIQUOTE") is candles
    record = resolver.get_record("MARKET_DATA", "BIQUOTE")
    assert record.provider is candles
    assert record.provider_id == "biquote"
    assert record.category == "market_data"


def test_ids_and_categories_are_normalized():
    registry = ProviderRegistry()
    provider = FakeMarketDataProvider()
    record = registry.register("  BiQuote  ", " Market_Data ", provider)
    assert record.provider_id == "biquote"
    assert record.category == "market_data"
    assert registry.get("MARKET_DATA", "biquote").provider is provider


@pytest.mark.parametrize("provider_id", ["", "   ", "1bad", "bi-quote", "BI QUOTE", 123, None])
def test_invalid_provider_id_rejected(provider_id):
    registry = ProviderRegistry()
    with pytest.raises(InvalidProviderRegistrationError):
        registry.register(provider_id, CATEGORY_MARKET_DATA, FakeMarketDataProvider())  # type: ignore[arg-type]


@pytest.mark.parametrize("category", ["", "   ", "candles", "bi-quote", 1, None])
def test_invalid_or_unknown_category_on_register(category):
    registry = ProviderRegistry()
    with pytest.raises((InvalidProviderRegistrationError, UnknownProviderCategoryError)):
        registry.register("biquote", category, FakeMarketDataProvider())  # type: ignore[arg-type]


def test_category_provider_mismatch_rejected():
    registry = ProviderRegistry()
    with pytest.raises(InvalidProviderRegistrationError, match="QuoteProvider"):
        registry.register("biquote_quote", CATEGORY_QUOTE, FakeMarketDataProvider())
    with pytest.raises(InvalidProviderRegistrationError, match="MarketDataProvider"):
        registry.register("biquote", CATEGORY_MARKET_DATA, FakeQuoteProvider())


def test_none_provider_rejected():
    registry = ProviderRegistry()
    with pytest.raises(InvalidProviderRegistrationError, match="required"):
        registry.register("biquote", CATEGORY_MARKET_DATA, None)


def test_duplicate_registration_fails_and_does_not_replace():
    registry = ProviderRegistry()
    first = FakeMarketDataProvider("first")
    second = FakeMarketDataProvider("second")
    registry.register("biquote", CATEGORY_MARKET_DATA, first)
    with pytest.raises(DuplicateProviderError):
        registry.register("biquote", CATEGORY_MARKET_DATA, second)
    assert registry.get(CATEGORY_MARKET_DATA, "biquote").provider is first


def test_same_id_allowed_in_different_categories():
    registry = ProviderRegistry()
    candles = FakeMarketDataProvider()
    quotes = FakeQuoteProvider()
    registry.register("biquote", CATEGORY_MARKET_DATA, candles)
    registry.register("biquote", CATEGORY_QUOTE, quotes)
    assert registry.get(CATEGORY_MARKET_DATA, "biquote").provider is candles
    assert registry.get(CATEGORY_QUOTE, "biquote").provider is quotes


def test_unknown_provider_id_fails_without_fallback():
    registry = ProviderRegistry()
    registry.register("other", CATEGORY_MARKET_DATA, FakeMarketDataProvider())
    resolver = ProviderResolver(registry)
    with pytest.raises(UnknownProviderError, match="biquote"):
        resolver.resolve_market_data("biquote")


def test_unknown_category_on_get_and_list_fails():
    registry = ProviderRegistry()
    with pytest.raises(UnknownProviderCategoryError):
        registry.get("news", "wire")
    with pytest.raises(UnknownProviderCategoryError):
        registry.list_providers("news")


def test_listing_is_sorted_independently_of_insertion_order():
    registry = ProviderRegistry()
    registry.register("zeta", CATEGORY_QUOTE, FakeQuoteProvider("zeta"))
    registry.register("alpha", CATEGORY_MARKET_DATA, FakeMarketDataProvider("alpha"))
    registry.register("mid", CATEGORY_MARKET_DATA, FakeMarketDataProvider("mid"))
    listed = registry.list_providers()
    assert [(item.category, item.provider_id) for item in listed] == [
        ("market_data", "alpha"),
        ("market_data", "mid"),
        ("quote", "zeta"),
    ]
    quote_only = registry.list_providers(CATEGORY_QUOTE)
    assert [item.provider_id for item in quote_only] == ["zeta"]


def test_register_list_resolve_do_not_activate_providers():
    registry = ProviderRegistry()
    candles = FakeMarketDataProvider()
    quotes = FakeQuoteProvider()
    registry.register("biquote", CATEGORY_MARKET_DATA, candles)
    registry.register("biquote_quote", CATEGORY_QUOTE, quotes)
    resolver = ProviderResolver(registry)
    registry.list_providers()
    resolver.resolve_market_data("biquote")
    resolver.resolve_quote("biquote_quote")
    resolver.list_records()
    assert candles.connect_calls == 0
    assert candles.fetch_calls == 0
    assert candles.close_calls == 0
    assert quotes.connect_calls == 0
    assert quotes.fetch_calls == 0
    assert quotes.close_calls == 0


def test_metadata_snapshot_from_describe_without_explicit_metadata():
    registry = ProviderRegistry()
    provider = FakeMarketDataProvider("snapshot")
    record = registry.register("biquote", CATEGORY_MARKET_DATA, provider)
    assert record.metadata["name"] == "snapshot"
    assert provider.describe_calls == 1
    listed = registry.list_providers()
    assert listed[0].metadata["name"] == "snapshot"
    assert provider.describe_calls == 1


def test_explicit_metadata_is_copied_and_describe_is_not_required():
    registry = ProviderRegistry()
    provider = FakeMarketDataProvider("ignored")
    supplied = {"label": "custom"}
    record = registry.register(
        "biquote",
        CATEGORY_MARKET_DATA,
        provider,
        metadata=supplied,
    )
    supplied["label"] = "mutated"
    assert record.metadata["label"] == "custom"
    assert provider.describe_calls == 0
    listed = registry.list_providers()[0]
    listed.metadata["label"] = "changed"
    assert registry.get(CATEGORY_MARKET_DATA, "biquote").metadata["label"] == "custom"


def test_invalid_metadata_type_rejected():
    registry = ProviderRegistry()
    with pytest.raises(InvalidProviderRegistrationError):
        registry.register(
            "biquote",
            CATEGORY_MARKET_DATA,
            FakeMarketDataProvider(),
            metadata=["nope"],  # type: ignore[arg-type]
        )


def test_extra_category_without_hardcoded_branch():
    class NewsProvider:
        pass

    registry = ProviderRegistry(extra_categories={"news": NewsProvider})
    news = NewsProvider()
    registry.register("wire", "news", news)
    resolver = ProviderResolver(registry)
    assert resolver.resolve("news", "wire") is news
    assert "news" in registry.supported_categories()


def test_resolver_requires_registry():
    with pytest.raises(InvalidProviderRegistrationError):
        ProviderResolver(None)  # type: ignore[arg-type]
    with pytest.raises(InvalidProviderRegistrationError):
        ProviderResolver(object())  # type: ignore[arg-type]


def test_lifecycle_remains_caller_owned_after_resolution():
    registry = ProviderRegistry()
    provider = FakeMarketDataProvider()
    registry.register("biquote", CATEGORY_MARKET_DATA, provider)
    resolved = ProviderResolver(registry).resolve_market_data("biquote")
    resolved.connect()
    resolved.fetch_candles("XAUUSD", "1h", 1)
    resolved.close()
    assert provider.connect_calls == 1
    assert provider.fetch_calls == 1
    assert provider.close_calls == 1


def test_contains_and_len_are_explicit_and_isolated():
    first = ProviderRegistry()
    second = ProviderRegistry()
    assert len(first) == 0
    assert first.contains(CATEGORY_MARKET_DATA, "biquote") is False
    first.register("biquote", CATEGORY_MARKET_DATA, FakeMarketDataProvider())
    assert len(first) == 1
    assert first.contains("MARKET_DATA", "BIQUOTE") is True
    assert second.contains(CATEGORY_MARKET_DATA, "biquote") is False
    assert len(second) == 0
    resolver = ProviderResolver(first)
    assert resolver.contains(CATEGORY_MARKET_DATA, "biquote") is True
    assert resolver.contains(CATEGORY_QUOTE, "biquote") is False


def test_contains_unknown_category_fails_without_fallback():
    registry = ProviderRegistry()
    with pytest.raises(UnknownProviderCategoryError):
        registry.contains("news", "wire")


def test_builtin_categories_cannot_be_replaced():
    class OtherPort:
        pass

    with pytest.raises(InvalidProviderRegistrationError, match="existing category"):
        ProviderRegistry(extra_categories={CATEGORY_MARKET_DATA: OtherPort})
    with pytest.raises(InvalidProviderRegistrationError, match="existing category"):
        ProviderRegistry(extra_categories={"News": OtherPort, "news": OtherPort})


def test_extra_categories_must_be_a_mapping_of_types():
    with pytest.raises(InvalidProviderRegistrationError, match="mapping"):
        ProviderRegistry(extra_categories=["news"])  # type: ignore[arg-type]
    with pytest.raises(InvalidProviderRegistrationError, match="type"):
        ProviderRegistry(extra_categories={"news": object()})  # type: ignore[arg-type]


def test_describe_failure_is_registration_error_and_does_not_register():
    class BrokenDescribe(FakeMarketDataProvider):
        def describe(self) -> Dict[str, Any]:
            raise RuntimeError("describe exploded")

    registry = ProviderRegistry()
    with pytest.raises(InvalidProviderRegistrationError, match="describe"):
        registry.register("biquote", CATEGORY_MARKET_DATA, BrokenDescribe())
    assert len(registry) == 0
    with pytest.raises(UnknownProviderError):
        registry.get(CATEGORY_MARKET_DATA, "biquote")


def test_default_categories_are_immutable():
    with pytest.raises(TypeError):
        from src.platform.services.provider_registry import DEFAULT_PROVIDER_CATEGORIES

        DEFAULT_PROVIDER_CATEGORIES["extra"] = object  # type: ignore[index]
    registry = ProviderRegistry()
    assert registry.supported_categories() == ("market_data", "quote")


def test_real_provider_ports_register_without_io():
    from src.platform.providers.biquote import BiQuoteProvider
    from src.platform.providers.biquote_quote import BiQuoteQuoteProvider

    candles = BiQuoteProvider()
    quotes = BiQuoteQuoteProvider()
    registry = ProviderRegistry()
    registry.register("biquote", CATEGORY_MARKET_DATA, candles)
    registry.register("biquote_quote", CATEGORY_QUOTE, quotes)
    resolver = ProviderResolver(registry)
    assert resolver.resolve_market_data("biquote") is candles
    assert resolver.resolve_quote("biquote_quote") is quotes
    listed = resolver.list_records()
    assert [item.provider_id for item in listed] == ["biquote", "biquote_quote"]

"""Part 6 focused tests for the ProviderValidationService."""

from typing import Any, Dict

import pytest

from src.platform.providers import MarketDataProvider, QuoteProvider
from src.platform.services import (
    CATEGORY_MARKET_DATA,
    CATEGORY_QUOTE,
    ProviderAccess,
    ProviderRegistry,
    ProviderValidationResult,
    ProviderValidationService,
)
from src.platform.services.provider_validation import (
    AVAILABILITY_AVAILABLE,
    AVAILABILITY_UNAVAILABLE,
    HEALTH_HEALTHY,
    HEALTH_UNAVAILABLE,
    HEALTH_UNHEALTHY,
    HEALTH_UNKNOWN,
    REASON_PROVIDER_CANNOT_BE_RESOLVED,
    REASON_PROVIDER_NOT_REGISTERED,
    REASON_PROVIDER_OPERATION_FAILED,
    REASON_REQUIRED_CAPABILITY_UNAVAILABLE,
)


class RecordingMarketDataProvider(MarketDataProvider):
    def __init__(self, describe_payload: Dict[str, Any], name: str = "rec-md") -> None:
        self._payload = describe_payload
        self._name = name
        self.connect_calls = 0
        self.fetch_calls = 0
        self.close_calls = 0
        self.describe_calls = 0

    def connect(self) -> None:
        self.connect_calls += 1

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100) -> list:
        self.fetch_calls += 1
        return []

    def close(self) -> None:
        self.close_calls += 1

    def describe(self) -> Dict[str, Any]:
        self.describe_calls += 1
        return {"name": self._name, **self._payload}


class RecordingQuoteProvider(QuoteProvider):
    def __init__(self, describe_payload: Dict[str, Any], name: str = "rec-qt") -> None:
        self._payload = describe_payload
        self._name = name
        self.connect_calls = 0
        self.fetch_calls = 0
        self.close_calls = 0
        self.describe_calls = 0

    def connect(self) -> None:
        self.connect_calls += 1

    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        self.fetch_calls += 1
        return {"symbol": symbol, "timestamp": 1}

    def close(self) -> None:
        self.close_calls += 1

    def describe(self) -> Dict[str, Any]:
        self.describe_calls += 1
        return {"name": self._name, **self._payload}


class ExplodingDescribeProvider(MarketDataProvider):
    def __init__(self) -> None:
        self.connect_calls = 0
        self.fetch_calls = 0
        self.close_calls = 0
        self.describe_calls = 0

    def connect(self) -> None:
        self.connect_calls += 1

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100) -> list:
        self.fetch_calls += 1
        return []

    def close(self) -> None:
        self.close_calls += 1

    def describe(self) -> Dict[str, Any]:
        self.describe_calls += 1
        raise RuntimeError("describe exploded")


def _build():
    md = RecordingMarketDataProvider(
        {
            "status": "connected",
            "supported_timeframes": ["1h", "4h"],
            "supported_symbols": ["XAUUSD"],
        }
    )
    qt = RecordingQuoteProvider(
        {"status": "available", "supported_symbols": ["XAUUSD", "EURUSD"]},
        name="rec-qt",
    )
    registry = ProviderRegistry()
    registry.register("md_one", CATEGORY_MARKET_DATA, md, metadata={})
    registry.register("qt_one", CATEGORY_QUOTE, qt, metadata={"region": "eu"})
    access = ProviderAccess(registry)
    service = ProviderValidationService(access)
    return md, qt, service


def test_construction_requires_provider_access():
    with pytest.raises(ValueError, match="ProviderAccess"):
        ProviderValidationService(None)
    with pytest.raises(ValueError, match="ProviderAccess"):
        ProviderValidationService(object())


def test_service_is_not_a_singleton():
    first = ProviderValidationService(ProviderAccess(ProviderRegistry()))
    second = ProviderValidationService(ProviderAccess(ProviderRegistry()))
    assert first is not second


def test_validate_explicit_market_data_identity_and_capabilities():
    md, qt, service = _build()
    result = service.validate(CATEGORY_MARKET_DATA, "md_one")
    assert isinstance(result, ProviderValidationResult)
    assert result.category == "market_data"
    assert result.provider_id == "md_one"
    assert result.availability == AVAILABILITY_AVAILABLE
    assert result.health == HEALTH_HEALTHY
    assert result.supports_candles is True
    assert result.supports_quotes is False
    assert result.name == "rec-md"
    assert result.supported_symbols == ("XAUUSD",)
    assert result.supported_timeframes == ("1h", "4h")
    assert result.reported_status == "connected"
    assert qt.describe_calls == 0
    assert md.connect_calls == 0
    assert md.fetch_calls == 0
    assert md.close_calls == 0


def test_validate_explicit_quote_identity_and_capabilities():
    _, qt, service = _build()
    result = service.validate(CATEGORY_QUOTE, "qt_one")
    assert result.category == "quote"
    assert result.provider_id == "qt_one"
    assert result.availability == AVAILABILITY_AVAILABLE
    assert result.health == HEALTH_HEALTHY
    assert result.supports_candles is False
    assert result.supports_quotes is True
    assert result.metadata["region"] == "eu"
    assert qt.connect_calls == 0
    assert qt.fetch_calls == 0
    assert qt.close_calls == 0


def test_unknown_provider_returns_unavailable_without_fallback():
    md, qt, service = _build()
    result = service.validate(CATEGORY_MARKET_DATA, "missing")
    assert result.provider_id == "missing"
    assert result.category == "market_data"
    assert result.availability == AVAILABILITY_UNAVAILABLE
    assert result.health == HEALTH_UNAVAILABLE
    assert result.reason == REASON_PROVIDER_NOT_REGISTERED
    assert result.supports_candles is False
    assert result.supports_quotes is False
    other = service.validate(CATEGORY_MARKET_DATA, "qt_one")
    assert other.availability == AVAILABILITY_UNAVAILABLE
    assert other.provider_id == "qt_one"
    assert md.fetch_calls == 0
    assert qt.fetch_calls == 0


def test_unknown_category_returns_unavailable_for_requested_identity():
    _, _, service = _build()
    result = service.validate("news", "wire")
    assert result.category == "news"
    assert result.provider_id == "wire"
    assert result.availability == AVAILABILITY_UNAVAILABLE
    assert result.health == HEALTH_UNAVAILABLE
    assert result.reason == REASON_PROVIDER_CANNOT_BE_RESOLVED


def test_no_implicit_provider_selection_on_empty_registry():
    service = ProviderValidationService(ProviderAccess(ProviderRegistry()))
    result = service.validate(CATEGORY_MARKET_DATA, "md_one")
    assert result.availability == AVAILABILITY_UNAVAILABLE
    assert result.health == HEALTH_UNAVAILABLE
    assert result.reason == REASON_PROVIDER_NOT_REGISTERED
    assert service.validate_all() == ()


def test_repeated_validation_is_deterministic():
    md, _, service = _build()
    first = service.validate(CATEGORY_MARKET_DATA, "md_one")
    second = service.validate(CATEGORY_MARKET_DATA, "md_one")
    assert first == second
    assert first.to_dict() == second.to_dict()
    assert md.describe_calls == 2
    assert md.connect_calls == 0
    assert md.fetch_calls == 0


def test_no_automatic_provider_switching():
    first = RecordingMarketDataProvider({"status": "connected"}, name="first")
    second = RecordingMarketDataProvider({"status": "available"}, name="second")
    registry = ProviderRegistry()
    registry.register("first", CATEGORY_MARKET_DATA, first, metadata={})
    registry.register("second", CATEGORY_MARKET_DATA, second, metadata={})
    service = ProviderValidationService(ProviderAccess(registry))
    result = service.validate(CATEGORY_MARKET_DATA, "first")
    assert result.provider_id == "first"
    assert result.name == "first"
    assert second.describe_calls == 0
    missing = service.validate(CATEGORY_MARKET_DATA, "third")
    assert missing.provider_id == "third"
    assert missing.availability == AVAILABILITY_UNAVAILABLE
    assert first.fetch_calls == 0
    assert second.fetch_calls == 0


def test_describe_failure_is_unhealthy_not_fallback():
    provider = ExplodingDescribeProvider()
    other = RecordingMarketDataProvider({"status": "connected"}, name="other")
    registry = ProviderRegistry()
    registry.register("broken", CATEGORY_MARKET_DATA, provider, metadata={})
    registry.register("other", CATEGORY_MARKET_DATA, other, metadata={})
    service = ProviderValidationService(ProviderAccess(registry))
    result = service.validate(CATEGORY_MARKET_DATA, "broken")
    assert result.provider_id == "broken"
    assert result.availability == AVAILABILITY_AVAILABLE
    assert result.health == HEALTH_UNHEALTHY
    assert result.reason == REASON_PROVIDER_OPERATION_FAILED
    assert "describe exploded" in str(result.detail)
    assert other.describe_calls == 0
    assert provider.connect_calls == 0
    assert provider.fetch_calls == 0
    assert provider.close_calls == 0


def test_required_capability_override_marks_unhealthy():
    md = RecordingMarketDataProvider(
        {"status": "connected", "supports_fetch_candles": False}
    )
    registry = ProviderRegistry()
    registry.register("md_one", CATEGORY_MARKET_DATA, md, metadata={})
    service = ProviderValidationService(ProviderAccess(registry))
    result = service.validate(CATEGORY_MARKET_DATA, "md_one")
    assert result.availability == AVAILABILITY_AVAILABLE
    assert result.health == HEALTH_UNHEALTHY
    assert result.supports_candles is False
    assert result.reason == REASON_REQUIRED_CAPABILITY_UNAVAILABLE


def test_reported_unhealthy_status_is_preserved():
    md = RecordingMarketDataProvider(
        {"status": "offline", "reason": "feed down"}
    )
    registry = ProviderRegistry()
    registry.register("md_one", CATEGORY_MARKET_DATA, md, metadata={})
    service = ProviderValidationService(ProviderAccess(registry))
    result = service.validate(CATEGORY_MARKET_DATA, "md_one")
    assert result.health == HEALTH_UNHEALTHY
    assert result.reported_status == "offline"
    assert result.reason == "feed down"


def test_unknown_reported_status_stays_unknown():
    md = RecordingMarketDataProvider({})
    registry = ProviderRegistry()
    registry.register("md_one", CATEGORY_MARKET_DATA, md, metadata={})
    service = ProviderValidationService(ProviderAccess(registry))
    result = service.validate(CATEGORY_MARKET_DATA, "md_one")
    assert result.availability == AVAILABILITY_AVAILABLE
    assert result.health == HEALTH_UNKNOWN
    assert result.supports_candles is True


def test_validate_all_preserves_explicit_identities():
    _, _, service = _build()
    results = service.validate_all()
    assert [(item.category, item.provider_id) for item in results] == [
        ("market_data", "md_one"),
        ("quote", "qt_one"),
    ]
    assert results[0].supports_candles is True
    assert results[1].supports_quotes is True


def test_construction_and_validation_never_connect_fetch_or_close():
    md, qt, service = _build()
    service.validate(CATEGORY_MARKET_DATA, "md_one")
    service.validate(CATEGORY_QUOTE, "qt_one")
    service.validate_all()
    assert md.connect_calls == 0
    assert md.fetch_calls == 0
    assert md.close_calls == 0
    assert qt.connect_calls == 0
    assert qt.fetch_calls == 0
    assert qt.close_calls == 0


def test_invalid_identity_is_unavailable_not_an_exception():
    _, _, service = _build()
    result = service.validate(CATEGORY_MARKET_DATA, "bi-quote")
    assert result.availability == AVAILABILITY_UNAVAILABLE
    assert result.health == HEALTH_UNAVAILABLE
    assert result.reason == REASON_PROVIDER_CANNOT_BE_RESOLVED
    assert result.provider_id == "bi-quote"


def test_biquote_validates_through_existing_contracts_without_io():
    from src.platform.providers.biquote import BiQuoteProvider
    from src.platform.providers.biquote_quote import BiQuoteQuoteProvider

    registry = ProviderRegistry()
    md = BiQuoteProvider()
    qt = BiQuoteQuoteProvider()
    registry.register("biquote", CATEGORY_MARKET_DATA, md, metadata={})
    registry.register("biquote_quote", CATEGORY_QUOTE, qt, metadata={})
    service = ProviderValidationService(ProviderAccess(registry))
    candles = service.validate(CATEGORY_MARKET_DATA, "biquote")
    quotes = service.validate(CATEGORY_QUOTE, "biquote_quote")
    assert candles.availability == AVAILABILITY_AVAILABLE
    assert candles.supports_candles is True
    assert candles.supports_quotes is False
    assert quotes.availability == AVAILABILITY_AVAILABLE
    assert quotes.supports_quotes is True
    assert quotes.supports_candles is False

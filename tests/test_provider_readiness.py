"""Tests for Part 13: Provider Readiness & Operational Gate."""

from typing import Any, Dict, List, Optional
import pytest

from src.platform.domain.provider_readiness import (
    PROVIDER_STATUS_NOT_READY,
    PROVIDER_STATUS_READY,
    ProviderReadiness,
)
from src.platform.domain.market import Candle
from src.platform.domain.quote import Quote
from src.platform.domain.availability import Availability
from src.platform.providers.market_data import MarketDataProvider
from src.platform.providers.quote import QuoteProvider
from src.platform.services.provider_registry import (
    CATEGORY_MARKET_DATA,
    CATEGORY_QUOTE,
    ProviderRegistry,
)
from src.platform.services.provider_access import ProviderAccess
from src.platform.services.provider_operations import ProviderOperations
from src.platform.services.provider_monitoring import ProviderMonitor
from src.platform.services.provider_readiness import (
    REASON_CAPABILITY_MISSING,
    REASON_DATA_STALE,
    REASON_PROVIDER_UNAVAILABLE,
    REASON_PROVIDER_UNHEALTHY,
    REASON_QUOTE_UNAVAILABLE,
    REASON_READY,
    ProviderReadinessService,
)


class DummyMarketDataProvider(MarketDataProvider):
    def __init__(
        self,
        provider_id: str = "dummy_md",
        status: str = "healthy",
        candles: Optional[List[Candle]] = None,
        describe_error: Optional[Exception] = None,
        supports_candles: bool = True,
    ):
        self._id = provider_id
        self._status = status
        self._raw_candles = candles or [
            Candle(
                timestamp=1000.0,
                open=100.0,
                high=105.0,
                low=99.0,
                close=102.0,
                volume=500.0,
            )
        ]
        self._describe_error = describe_error
        self._supports_candles = supports_candles

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def describe(self) -> Dict[str, Any]:
        if self._describe_error:
            raise self._describe_error
        return {
            "name": f"Dummy MD {self._id}",
            "status": self._status,
            "supports_fetch_candles": self._supports_candles,
            "supported_symbols": ["XAUUSD"],
            "supported_timeframes": ["1h"],
        }

    def fetch_candles(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        return [
            {
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in self._raw_candles
        ]


class DummyQuoteProvider(QuoteProvider):
    def __init__(
        self,
        provider_id: str = "dummy_qp",
        status: str = "healthy",
        quote: Optional[Quote] = None,
        describe_error: Optional[Exception] = None,
        supports_quote: bool = True,
    ):
        self._id = provider_id
        self._status = status
        self._quote = quote or Quote(
            symbol="XAUUSD",
            timestamp=1000.0,
            bid=2000.0,
            ask=2001.0,
            availability=Availability(status="live"),
        )
        self._describe_error = describe_error
        self._supports_quote = supports_quote

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def describe(self) -> Dict[str, Any]:
        if self._describe_error:
            raise self._describe_error
        return {
            "name": f"Dummy Quote {self._id}",
            "status": self._status,
            "supports_fetch_quote": self._supports_quote,
            "supported_symbols": ["XAUUSD"],
        }

    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "symbol": self._quote.symbol,
            "timestamp": self._quote.timestamp,
            "bid": self._quote.bid,
            "ask": self._quote.ask,
        }
        if self._quote.availability is not None:
            res["availability"] = self._quote.availability.to_dict()
        return res


def test_ready_provider():
    registry = ProviderRegistry()
    provider = DummyMarketDataProvider(status="healthy")
    registry.register("md_ready", CATEGORY_MARKET_DATA, provider)
    access = ProviderAccess(registry)

    service = ProviderReadinessService(access)
    result = service.assess(CATEGORY_MARKET_DATA, "md_ready")

    assert result.status == PROVIDER_STATUS_READY
    assert result.is_ready is True
    assert result.reason == REASON_READY
    assert result.health == "healthy"
    assert result.category == CATEGORY_MARKET_DATA
    assert result.provider_id == "md_ready"


def test_unhealthy_provider():
    registry = ProviderRegistry()
    provider = DummyMarketDataProvider(status="unhealthy")
    registry.register("md_unhealthy", CATEGORY_MARKET_DATA, provider)
    access = ProviderAccess(registry)

    service = ProviderReadinessService(access)
    result = service.assess(CATEGORY_MARKET_DATA, "md_unhealthy")

    assert result.status == PROVIDER_STATUS_NOT_READY
    assert result.is_ready is False
    assert result.reason == REASON_PROVIDER_UNHEALTHY
    assert result.health == "unhealthy"


def test_unavailable_unregistered_provider():
    registry = ProviderRegistry()
    access = ProviderAccess(registry)

    service = ProviderReadinessService(access)
    result = service.assess(CATEGORY_MARKET_DATA, "md_unknown")

    assert result.status == PROVIDER_STATUS_NOT_READY
    assert result.is_ready is False
    assert result.reason == "provider not registered"
    assert result.health == "unavailable"


def test_missing_capability():
    registry = ProviderRegistry()
    provider = DummyMarketDataProvider(supports_candles=False)
    registry.register("md_nocandles", CATEGORY_MARKET_DATA, provider)
    access = ProviderAccess(registry)

    service = ProviderReadinessService(access)
    result = service.assess(CATEGORY_MARKET_DATA, "md_nocandles")

    assert result.status == PROVIDER_STATUS_NOT_READY
    assert result.is_ready is False
    assert result.reason == REASON_CAPABILITY_MISSING


def test_stale_freshness_condition():
    registry = ProviderRegistry()
    # Candle timestamp is 1000.0
    provider = DummyMarketDataProvider(
        candles=[
            Candle(
                timestamp=1000.0,
                open=100.0,
                high=105.0,
                low=99.0,
                close=102.0,
                volume=500.0,
            )
        ]
    )
    registry.register("md_stale", CATEGORY_MARKET_DATA, provider)
    access = ProviderAccess(registry)
    ops = ProviderOperations(access)
    monitor = ProviderMonitor(ops)

    service = ProviderReadinessService(access, monitor=monitor)
    # Reference instant is 2000.0 -> age is 1000 seconds > max_age_seconds (60)
    result = service.assess(
        CATEGORY_MARKET_DATA,
        "md_stale",
        symbol="XAUUSD",
        timeframe="1h",
        reference=2000.0,
        max_age_seconds=60.0,
    )

    assert result.status == PROVIDER_STATUS_NOT_READY
    assert result.is_ready is False
    assert result.reason == REASON_DATA_STALE
    assert result.freshness is not None
    assert result.freshness["freshness"]["status"] == "stale"


def test_quote_unavailable_freshness_condition():
    registry = ProviderRegistry()
    quote = Quote(
        symbol="XAUUSD",
        timestamp=1000.0,
        bid=2000.0,
        ask=2001.0,
        availability=Availability(status="unavailable", reason="market closed"),
    )
    provider = DummyQuoteProvider(quote=quote)
    registry.register("qp_unavail", CATEGORY_QUOTE, provider)
    access = ProviderAccess(registry)
    ops = ProviderOperations(access)
    monitor = ProviderMonitor(ops)

    service = ProviderReadinessService(access, monitor=monitor)
    result = service.assess(
        CATEGORY_QUOTE,
        "qp_unavail",
        symbol="XAUUSD",
        reference=1005.0,
    )

    assert result.status == PROVIDER_STATUS_NOT_READY
    assert result.is_ready is False
    assert result.reason == REASON_QUOTE_UNAVAILABLE


def test_result_structure_and_to_dict():
    readiness = ProviderReadiness(
        category=CATEGORY_MARKET_DATA,
        provider_id="md_test",
        status=PROVIDER_STATUS_READY,
        reason=REASON_READY,
        health="healthy",
        capabilities={"supports_fetch_candles": True},
        metadata={"key": "val"},
        detail="all good",
    )

    d = readiness.to_dict()
    assert d["category"] == CATEGORY_MARKET_DATA
    assert d["provider_id"] == "md_test"
    assert d["status"] == PROVIDER_STATUS_READY
    assert d["is_ready"] is True
    assert d["reason"] == REASON_READY
    assert d["health"] == "healthy"
    assert d["capabilities"] == {"supports_fetch_candles": True}
    assert d["metadata"] == {"key": "val"}
    assert d["detail"] == "all good"


def test_multiple_providers_and_assess_all():
    registry = ProviderRegistry()
    md1 = DummyMarketDataProvider(provider_id="md1", status="healthy")
    md2 = DummyMarketDataProvider(provider_id="md2", status="unhealthy")
    qp1 = DummyQuoteProvider(provider_id="qp1", status="healthy")

    registry.register("md1", CATEGORY_MARKET_DATA, md1)
    registry.register("md2", CATEGORY_MARKET_DATA, md2)
    registry.register("qp1", CATEGORY_QUOTE, qp1)

    access = ProviderAccess(registry)
    service = ProviderReadinessService(access)

    results = service.assess_all()
    assert len(results) == 3

    res_dict = {(r.category, r.provider_id): r for r in results}
    assert res_dict[(CATEGORY_MARKET_DATA, "md1")].status == PROVIDER_STATUS_READY
    assert res_dict[(CATEGORY_MARKET_DATA, "md2")].status == PROVIDER_STATUS_NOT_READY
    assert res_dict[(CATEGORY_QUOTE, "qp1")].status == PROVIDER_STATUS_READY


def test_empty_registry_assess_all():
    registry = ProviderRegistry()
    access = ProviderAccess(registry)
    service = ProviderReadinessService(access)

    results = service.assess_all()
    assert results == ()


def test_compatibility_with_existing_provider_monitoring():
    registry = ProviderRegistry()
    md_provider = DummyMarketDataProvider(
        candles=[
            Candle(
                timestamp=1000.0,
                open=100.0,
                high=105.0,
                low=99.0,
                close=102.0,
                volume=500.0,
            )
        ]
    )
    registry.register("md_fresh", CATEGORY_MARKET_DATA, md_provider)
    access = ProviderAccess(registry)
    ops = ProviderOperations(access)
    monitor = ProviderMonitor(ops)

    service = ProviderReadinessService(access, monitor=monitor)
    # Fresh data (timestamp 1000.0, reference 1010.0 -> age 10s < max_age 60s)
    result = service.assess(
        CATEGORY_MARKET_DATA,
        "md_fresh",
        symbol="XAUUSD",
        timeframe="1h",
        reference=1010.0,
        max_age_seconds=60.0,
    )

    assert result.status == PROVIDER_STATUS_READY
    assert result.is_ready is True
    assert result.reason == REASON_READY
    assert result.freshness is not None
    assert result.freshness["freshness"]["status"] == "fresh"

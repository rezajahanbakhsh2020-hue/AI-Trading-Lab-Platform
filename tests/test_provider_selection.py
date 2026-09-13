"""Tests for Part 14: Provider Selection & Operational Routing."""

from typing import Any, Dict, List, Optional
import pytest

from src.platform.domain.provider_selection import (
    SELECTION_STATUS_NOT_AVAILABLE,
    SELECTION_STATUS_SELECTED,
    ProviderSelection,
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
from src.platform.services.provider_readiness import ProviderReadinessService
from src.platform.services.provider_selection import ProviderSelectionService


class DummyMarketDataProvider(MarketDataProvider):
    def __init__(
        self,
        provider_id: str = "dummy_md",
        status: str = "healthy",
        candles: Optional[List[Candle]] = None,
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
        self._supports_candles = supports_candles

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def describe(self) -> Dict[str, Any]:
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
        self._supports_quote = supports_quote

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def describe(self) -> Dict[str, Any]:
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


def _build_services(registry: ProviderRegistry):
    access = ProviderAccess(registry)
    ops = ProviderOperations(access)
    monitor = ProviderMonitor(ops)
    readiness_svc = ProviderReadinessService(access, monitor=monitor)
    selection_svc = ProviderSelectionService(readiness_svc)
    return access, readiness_svc, selection_svc


def test_1_one_ready_provider_selected():
    registry = ProviderRegistry()
    md = DummyMarketDataProvider("md1", status="healthy")
    registry.register("md1", CATEGORY_MARKET_DATA, md)
    _, _, selection_svc = _build_services(registry)

    selection = selection_svc.select_provider(CATEGORY_MARKET_DATA)
    assert selection.status == SELECTION_STATUS_SELECTED
    assert selection.is_selected is True
    assert selection.selected_provider_id == "md1"
    assert selection.readiness is not None
    assert selection.readiness.is_ready is True


def test_2_preferred_ready_provider_selected():
    registry = ProviderRegistry()
    md1 = DummyMarketDataProvider("md1", status="healthy")
    md2 = DummyMarketDataProvider("md2", status="healthy")
    registry.register("md1", CATEGORY_MARKET_DATA, md1)
    registry.register("md2", CATEGORY_MARKET_DATA, md2)
    _, _, selection_svc = _build_services(registry)

    selection = selection_svc.select_provider(CATEGORY_MARKET_DATA, preferred_provider_id="md2")
    assert selection.status == SELECTION_STATUS_SELECTED
    assert selection.selected_provider_id == "md2"
    assert selection.preferred_provider_id == "md2"
    assert selection.preferred_rejected_reason is None


def test_3_preferred_provider_missing_fallback():
    registry = ProviderRegistry()
    md1 = DummyMarketDataProvider("md1", status="healthy")
    registry.register("md1", CATEGORY_MARKET_DATA, md1)
    _, _, selection_svc = _build_services(registry)

    selection = selection_svc.select_provider(CATEGORY_MARKET_DATA, preferred_provider_id="missing_md")
    assert selection.status == SELECTION_STATUS_SELECTED
    assert selection.selected_provider_id == "md1"
    assert selection.preferred_provider_id == "missing_md"
    assert selection.preferred_rejected_reason == "provider not registered"


def test_4_preferred_provider_not_ready_fallback():
    registry = ProviderRegistry()
    md1 = DummyMarketDataProvider("md1", status="unhealthy")
    md2 = DummyMarketDataProvider("md2", status="healthy")
    registry.register("md1", CATEGORY_MARKET_DATA, md1)
    registry.register("md2", CATEGORY_MARKET_DATA, md2)
    _, _, selection_svc = _build_services(registry)

    selection = selection_svc.select_provider(CATEGORY_MARKET_DATA, preferred_provider_id="md1")
    assert selection.status == SELECTION_STATUS_SELECTED
    assert selection.selected_provider_id == "md2"
    assert selection.preferred_provider_id == "md1"
    assert selection.preferred_rejected_reason == "provider is unhealthy"


def test_5_multiple_ready_providers_deterministic_order():
    registry = ProviderRegistry()
    # Registrations in non-alphabetical order
    md_b = DummyMarketDataProvider("b_md", status="healthy")
    md_a = DummyMarketDataProvider("a_md", status="healthy")
    registry.register("b_md", CATEGORY_MARKET_DATA, md_b)
    registry.register("a_md", CATEGORY_MARKET_DATA, md_a)
    _, _, selection_svc = _build_services(registry)

    # list_providers is sorted by category, provider_id -> 'a_md' comes before 'b_md'
    selection = selection_svc.select_provider(CATEGORY_MARKET_DATA)
    assert selection.status == SELECTION_STATUS_SELECTED
    assert selection.selected_provider_id == "a_md"


def test_6_no_ready_providers_structured_not_available():
    registry = ProviderRegistry()
    md1 = DummyMarketDataProvider("md1", status="unhealthy")
    registry.register("md1", CATEGORY_MARKET_DATA, md1)
    _, _, selection_svc = _build_services(registry)

    selection = selection_svc.select_provider(CATEGORY_MARKET_DATA)
    assert selection.status == SELECTION_STATUS_NOT_AVAILABLE
    assert selection.is_selected is False
    assert selection.selected_provider_id is None
    assert selection.readiness is None


def test_7_empty_registry_structured_not_available():
    registry = ProviderRegistry()
    _, _, selection_svc = _build_services(registry)

    selection = selection_svc.select_provider(CATEGORY_MARKET_DATA)
    assert selection.status == SELECTION_STATUS_NOT_AVAILABLE
    assert selection.is_selected is False
    assert selection.selected_provider_id is None


def test_8_readiness_reasons_and_structure_preserved():
    registry = ProviderRegistry()
    md1 = DummyMarketDataProvider("md1", status="healthy")
    registry.register("md1", CATEGORY_MARKET_DATA, md1)
    _, _, selection_svc = _build_services(registry)

    selection = selection_svc.select_provider(CATEGORY_MARKET_DATA)
    d = selection.to_dict()
    assert d["category"] == CATEGORY_MARKET_DATA
    assert d["status"] == SELECTION_STATUS_SELECTED
    assert d["is_selected"] is True
    assert d["selected_provider_id"] == "md1"
    assert d["readiness"]["status"] == "READY"


def test_9_selection_never_chooses_not_ready():
    registry = ProviderRegistry()
    md1 = DummyMarketDataProvider("md1", status="unhealthy")
    md2 = DummyMarketDataProvider("md2", supports_candles=False)
    registry.register("md1", CATEGORY_MARKET_DATA, md1)
    registry.register("md2", CATEGORY_MARKET_DATA, md2)
    _, _, selection_svc = _build_services(registry)

    selection = selection_svc.select_provider(CATEGORY_MARKET_DATA)
    assert selection.status == SELECTION_STATUS_NOT_AVAILABLE
    assert selection.selected_provider_id is None


def test_10_delegates_to_readiness_service():
    class TrackingReadinessService(ProviderReadinessService):
        def __init__(self, access, monitor):
            super().__init__(access, monitor)
            self.calls = []

        def assess(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            return super().assess(*args, **kwargs)

    registry = ProviderRegistry()
    md1 = DummyMarketDataProvider("md1", status="healthy")
    registry.register("md1", CATEGORY_MARKET_DATA, md1)
    access = ProviderAccess(registry)
    ops = ProviderOperations(access)
    monitor = ProviderMonitor(ops)
    tracking_readiness = TrackingReadinessService(access, monitor)
    selection_svc = ProviderSelectionService(tracking_readiness)

    selection = selection_svc.select_provider(CATEGORY_MARKET_DATA)
    assert len(tracking_readiness.calls) >= 1
    assert selection.status == SELECTION_STATUS_SELECTED


def test_11_deterministic_registration_order_semantics():
    registry = ProviderRegistry()
    qp1 = DummyQuoteProvider("qp1", status="healthy")
    qp2 = DummyQuoteProvider("qp2", status="healthy")
    registry.register("qp1", CATEGORY_QUOTE, qp1)
    registry.register("qp2", CATEGORY_QUOTE, qp2)
    _, _, selection_svc = _build_services(registry)

    sel1 = selection_svc.select_provider(CATEGORY_QUOTE)
    sel2 = selection_svc.select_provider(CATEGORY_QUOTE)
    assert sel1.selected_provider_id == sel2.selected_provider_id == "qp1"


def test_12_compatibility_with_existing_monitoring():
    registry = ProviderRegistry()
    # Candle at timestamp 1000.0, reference 1010.0 -> fresh (10s age < max_age 60s)
    md1 = DummyMarketDataProvider(
        "md1",
        candles=[
            Candle(
                timestamp=1000.0,
                open=100.0,
                high=105.0,
                low=99.0,
                close=102.0,
                volume=500.0,
            )
        ],
    )
    registry.register("md1", CATEGORY_MARKET_DATA, md1)
    _, _, selection_svc = _build_services(registry)

    selection = selection_svc.select_provider(
        CATEGORY_MARKET_DATA,
        symbol="XAUUSD",
        timeframe="1h",
        reference=1010.0,
        max_age_seconds=60.0,
    )
    assert selection.status == SELECTION_STATUS_SELECTED
    assert selection.selected_provider_id == "md1"
    assert selection.readiness is not None
    assert selection.readiness.freshness is not None
    assert selection.readiness.freshness["freshness"]["status"] == "fresh"

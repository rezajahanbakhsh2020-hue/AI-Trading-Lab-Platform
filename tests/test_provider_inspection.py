"""Part 9 focused tests for the ProviderInspectionService."""

from typing import Any, Dict

import pytest

from src.platform.providers.market_data import MarketDataProvider
from src.platform.providers.quote import QuoteProvider
from src.platform.services import (
    CATEGORY_MARKET_DATA,
    CATEGORY_QUOTE,
    ProviderAccess,
    ProviderInspectionService,
    ProviderRegistry,
    UnknownProviderCategoryError,
    UnknownProviderError,
)
from src.platform.services.provider_inspection import (
    HEALTH_STATUS_AVAILABLE,
    HEALTH_STATUS_CONNECTED,
    HEALTH_STATUS_ERROR,
    HEALTH_STATUS_UNKNOWN,
)


class RecordingMarketDataProvider(MarketDataProvider):
    """Market-data port double recording lifecycle calls."""

    def __init__(
        self, describe_payload: Dict[str, Any], name: str = "rec-md"
    ) -> None:
        self._payload = describe_payload
        self._name = name
        self.connect_calls = 0
        self.fetch_calls = 0
        self.close_calls =  0
        self.describe_calls =  0

    def connect(self) -> None:
        self.connect_calls +=  1

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100) -> list:
        self.fetch_calls +=  1
        return []

    def close(self) -> None:
        self.close_calls +=  1

    def describe(self) -> Dict[str, Any]:
        self.describe_calls +=  1
        return {"name": self._name, **self._payload}


class RecordingQuoteProvider(QuoteProvider):
    """Quote port double recording lifecycle calls."""

    def __init__(
        self, describe_payload: Dict[str, Any], name: str = "rec-qt"
    ) -> None:
        self._payload = describe_payload
        self._name = name
        self.connect_calls = 0
        self.fetch_calls =  0
        self.close_calls =  0
        self.describe_calls =  0

    def connect(self) -> None:
        self.connect_calls +=  1

    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        self.fetch_calls +=  1
        return {"symbol": symbol, "timestamp": 1}

    def close(self) -> None:
        self.close_calls +=  1

    def describe(self) -> Dict[str, Any]:
        self.describe_calls +=  1
        return {"name": self._name, **self._payload}


class ExplodingDescribeProvider(MarketDataProvider):
    """Market-data double whose describe() raises like a real provider bug."""

    def connect(self) -> None:
        return None

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100) -> list:
        return []

    def close(self) -> None:
        return None

    def describe(self) -> Dict[str, Any]:
        raise RuntimeError("describe exploded")


def _build():
    md = RecordingMarketDataProvider(
        {"status": "connected",
         "supported_timeframes": ["1h", "4h"],
         "supported_symbols": ["XAUUSD"],
         "supports_fetch_candles": True}
    )
    qt = RecordingQuoteProvider(
        {"status": "available", "supported_symbols": ["XAUUSD", "EURUSD"]},
        name="rec-qt",
    )
    registry = ProviderRegistry()
    registry.register("md_one", CATEGORY_MARKET_DATA, md, metadata={})
    registry.register("qt_one", CATEGORY_QUOTE, qt, metadata={"region": "eu"})
    access = ProviderAccess(registry)
    service = ProviderInspectionService(access)
    return md, qt, service


def test_construction_requires_provider_access():
    with pytest.raises(ValueError, match="ProviderAccess"):
        ProviderInspectionService(None)


def test_unknown_provider_category_propagates():
    _, _, service = _build()
    with pytest.raises(UnknownProviderCategoryError):
        service.inspect("bogus", "md_one")


def test_unknown_provider_id_propagates():
    _, _, service = _build()
    with pytest.raises(UnknownProviderError):
        service.inspect(CATEGORY_MARKET_DATA, "missing")
    with pytest.raises(UnknownProviderError):
        service.inspect(CATEGORY_QUOTE, "missing")


def test_construction_does_not_connect_or_fetch_or_close():
    md, qt, service = _build()
    assert md.connect_calls ==  0
    assert md.fetch_calls ==  0
    assert md.close_calls ==  0
    assert qt.connect_calls ==  0
    assert qt.fetch_calls ==  0
    assert qt.close_calls ==  0


def test_inspect_never_performs_io():
    md, qt, service = _build()
    result = service.inspect(CATEGORY_MARKET_DATA, "md_one")
    assert md.connect_calls ==  0
    assert md.fetch_calls ==  0
    assert md.close_calls ==  0
    assert md.describe_calls ==  1
    assert qt.connect_calls ==  0
    assert qt.fetch_calls ==  0
    assert qt.close_calls ==  0
    assert qt.describe_calls ==  0
    assert result.health.status == HEALTH_STATUS_CONNECTED


def test_inspect_all_never_performs_io():
    md, qt, service = _build()
    results = service.inspect_all()
    assert len(results) == 2
    assert md.connect_calls ==  0
    assert md.fetch_calls ==  0
    assert md.close_calls ==  0
    assert qt.connect_calls ==  0
    assert qt.fetch_calls ==  0
    assert qt.close_calls ==  0
    assert md.describe_calls ==  1
    assert qt.describe_calls ==  1

def test_registration_without_metadata_snapshots_describe_once():
    provider = RecordingMarketDataProvider({"status": "connected"})
    registry = ProviderRegistry()
    registry.register("md_one", CATEGORY_MARKET_DATA, provider)
    assert provider.describe_calls == 1
    record = registry.get(CATEGORY_MARKET_DATA, "md_one")
    assert record.metadata == {"name": "rec-md", "status": "connected"}

import pytest
from typing import Any, Dict, List

from src.platform.adapters import ProviderAdapter
from src.platform.adapter import Adapter
from src.platform.providers import MarketDataProvider


class FakeMarketDataProvider(MarketDataProvider):
    def __init__(self, data: List[Dict[str, Any]] = None, to_raise: Exception = None):
        self._data = list(data) if data is not None else []
        self._to_raise = to_raise
        self.connected = False
        self.closed = False
        self.last_called = None

    def connect(self) -> None:
        self.connected = True

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        # Record parameters for verification
        self.last_called = {"symbol": symbol, "timeframe": timeframe, "limit": limit}
        if self._to_raise:
            raise self._to_raise
        return self._data[:limit]

    def close(self) -> None:
        self.closed = True

    def describe(self) -> Dict[str, Any]:
        return {"name": "FakeMarketDataProvider", "stored": len(self._data)}


def test_provider_adapter_importable_and_is_adapter():
    assert ProviderAdapter is not None
    assert issubclass(ProviderAdapter, Adapter)


def test_constructor_accepts_market_data_provider():
    p = FakeMarketDataProvider([])
    adapter = ProviderAdapter(p)
    assert adapter is not None


def test_connect_and_close_delegate_once():
    p = FakeMarketDataProvider([])
    adapter = ProviderAdapter(p)
    assert not p.connected
    adapter.connect()
    assert p.connected
    assert not p.closed
    adapter.close()
    assert p.closed


def test_fetch_delegates_and_forwards_parameters_and_preserves_records():
    data = [
        {"timestamp": "t1", "open": 1, "high": 2, "low": 0.5, "close": 1.5},
        {"timestamp": "t2", "open": 2, "high": 3, "low": 1.5, "close": 2.5, "volume": 100},
    ]
    p = FakeMarketDataProvider(data)
    adapter = ProviderAdapter(p)
    out = adapter.fetch_market_data("SYM", "1d", limit=2)

    # ensure parameters forwarded exactly
    assert p.last_called == {"symbol": "SYM", "timeframe": "1d", "limit": 2}

    # returned records are preserved exactly and order preserved
    assert out == data
    assert isinstance(out[0], dict)

    # optional volume preserved
    assert "volume" not in out[0]
    assert out[1]["volume"] == 100

    # ProviderAdapter.describe delegates
    desc = adapter.describe()
    assert isinstance(desc, dict)
    assert desc.get("name") == "FakeMarketDataProvider"


def test_provider_exceptions_propagate():
    p = FakeMarketDataProvider([], to_raise=RuntimeError("provider error"))
    adapter = ProviderAdapter(p)
    with pytest.raises(RuntimeError):
        adapter.fetch_market_data("SYM", "1d", 1)


def test_no_candle_conversion_or_fabrication():
    # Ensure adapter returns raw dicts and does not fabricate missing fields like volume
    data = [{"timestamp": 123, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}]
    p = FakeMarketDataProvider(data)
    adapter = ProviderAdapter(p)
    out = adapter.fetch_market_data("SYM", "1d", 1)
    assert isinstance(out[0], dict)
    assert out[0].get("volume") is None


def test_adapter_and_provider_separate_abstractions():
    # Ensure ProviderAdapter is an Adapter and MarketDataProvider remains separate
    assert issubclass(ProviderAdapter, Adapter)
    assert MarketDataProvider is not Adapter

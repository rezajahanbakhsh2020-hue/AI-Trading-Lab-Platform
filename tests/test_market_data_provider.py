import pytest
from typing import Any, Dict, List

from src.platform.providers import MarketDataProvider


def test_market_data_provider_importable_and_abstract():
    # Importable
    assert MarketDataProvider is not None
    # Abstract - cannot instantiate directly
    with pytest.raises(TypeError):
        MarketDataProvider()  # type: ignore


class FakeMarketDataProvider(MarketDataProvider):
    """Test-only fake provider used solely inside tests as a fixture.

    This class is part of test infrastructure and must not be placed under
    src/ in production code.
    """

    def __init__(self, data: List[Dict[str, Any]] = None, to_raise: Exception = None):
        self._data = list(data) if data is not None else []
        self._to_raise = to_raise
        self.connected = False
        self.closed = False

    def connect(self) -> None:
        self.connected = True

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        if self._to_raise:
            raise self._to_raise
        # Return raw dicts; do not fabricate fields. Respect limit.
        return self._data[:limit]

    def close(self) -> None:
        self.closed = True

    def describe(self) -> Dict[str, Any]:
        return {"name": "FakeMarketDataProvider", "stored": len(self._data)}


def test_fake_provider_lifecycle_and_fetch():
    data = [
        {"timestamp": 1, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5},
        {"timestamp": 2, "open": 2.0, "high": 3.0, "low": 1.5, "close": 2.5, "volume": 100},
    ]
    p = FakeMarketDataProvider(data)

    # connect
    assert not p.connected
    p.connect()
    assert p.connected

    # fetch raw dicts
    out = p.fetch_candles("SYM", "1d", limit=10)
    assert isinstance(out, list)
    assert isinstance(out[0], dict)

    # timestamp preserved
    assert out[0]["timestamp"] == 1

    # OHLC preserved
    assert out[0]["open"] == 1.0
    assert out[0]["high"] == 2.0
    assert out[0]["low"] == 0.5
    assert out[0]["close"] == 1.5

    # volume optional on first record, present on second
    assert "volume" not in out[0]
    assert "volume" in out[1] and out[1]["volume"] == 100

    # describe
    desc = p.describe()
    assert isinstance(desc, dict)

    # close
    assert not p.closed
    p.close()
    assert p.closed


def test_provider_exceptions_propagate_and_limit_respected():
    p = FakeMarketDataProvider([], to_raise=RuntimeError("provider failure"))
    p.connect()
    with pytest.raises(RuntimeError):
        p.fetch_candles("SYM", "1d", 1)

    # limit behavior
    data = [
        {"timestamp": "t1", "open": 1, "high": 1, "low": 1, "close": 1},
        {"timestamp": "t2", "open": 2, "high": 2, "low": 2, "close": 2},
    ]
    p2 = FakeMarketDataProvider(data)
    out = p2.fetch_candles("S", "1h", limit=1)
    assert len(out) == 1
    assert out[0]["timestamp"] == "t1"


def test_provider_does_not_convert_to_domain_objects():
    data = [{"timestamp": "ts", "open": 1, "high": 1, "low": 1, "close": 1}]
    p = FakeMarketDataProvider(data)
    out = p.fetch_candles("SYM", "1d", 1)
    # Provider returns raw dicts; conversion to Candle happens in service layer
    assert isinstance(out[0], dict)

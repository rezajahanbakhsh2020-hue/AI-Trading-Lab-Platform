import pytest

from src.platform.services import MarketDataService
from src.platform.domain.market import Candle
from src.platform.adapter import Adapter


class FakeAdapter(Adapter):
    def __init__(self, to_return=None, to_raise=None):
        self.to_return = to_return if to_return is not None else []
        self.to_raise = to_raise
        self.last_called = None

    def connect(self) -> None:
        pass

    def fetch_market_data(self, symbol: str, timeframe: str, limit: int = 100):
        # record call
        self.last_called = {"symbol": symbol, "timeframe": timeframe, "limit": limit}
        if self.to_raise:
            raise self.to_raise
        return self.to_return

    def close(self) -> None:
        pass


def test_service_accepts_adapter():
    adapter = FakeAdapter([])
    svc = MarketDataService(adapter)
    assert svc is not None


def test_valid_adapter_candle_becomes_candle():
    rec = {"timestamp": 1234567890, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 100}
    adapter = FakeAdapter([rec])
    svc = MarketDataService(adapter)
    candles = svc.get_candles("XAUUSD", "1d", 1)
    assert len(candles) == 1
    c = candles[0]
    assert isinstance(c, Candle)
    assert c.to_dict()["timestamp"] == rec["timestamp"]
    assert c.open == float(rec["open"]) and c.high == float(rec["high"]) and c.low == float(rec["low"]) and c.close == float(rec["close"]) and c.volume == float(rec["volume"])


def test_multiple_candles_preserve_order():
    recs = [
        {"timestamp": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5},
        {"timestamp": 2, "open": 2, "high": 3, "low": 1.5, "close": 2.5},
    ]
    adapter = FakeAdapter(recs)
    svc = MarketDataService(adapter)
    candles = svc.get_candles("SYM", "1h", 2)
    assert [c.timestamp for c in candles] == [1, 2]


def test_timestamp_preserved_string():
    rec = {"timestamp": "2020-01-01T00:00:00Z", "open": 1, "high": 1, "low": 1, "close": 1}
    adapter = FakeAdapter([rec])
    svc = MarketDataService(adapter)
    candles = svc.get_candles("SYM", "1d", 1)
    assert candles[0].timestamp == rec["timestamp"]


def test_volume_preserved_and_missing_volume_becomes_none():
    rec_with_vol = {"timestamp": 1, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 0}
    rec_no_vol = {"timestamp": 2, "open": 1, "high": 1, "low": 1, "close": 1}
    adapter = FakeAdapter([rec_with_vol, rec_no_vol])
    svc = MarketDataService(adapter)
    candles = svc.get_candles("SYM", "1d", 2)
    assert candles[0].volume == 0.0
    assert candles[1].volume is None


@pytest.mark.parametrize("missing_field", ["timestamp", "open", "high", "low", "close"])
def test_missing_required_field_raises(missing_field):
    rec = {"timestamp": 1, "open": 1, "high": 1, "low": 1, "close": 1}
    rec.pop(missing_field)
    adapter = FakeAdapter([rec])
    svc = MarketDataService(adapter)
    with pytest.raises(ValueError):
        svc.get_candles("SYM", "1d", 1)


def test_invalid_symbol_type_raises():
    adapter = FakeAdapter([])
    svc = MarketDataService(adapter)
    with pytest.raises(ValueError):
        svc.get_candles(123, "1d", 1)  # type: ignore


def test_blank_symbol_raises():
    adapter = FakeAdapter([])
    svc = MarketDataService(adapter)
    with pytest.raises(ValueError):
        svc.get_candles("   ", "1d", 1)


def test_invalid_timeframe_type_raises():
    adapter = FakeAdapter([])
    svc = MarketDataService(adapter)
    with pytest.raises(ValueError):
        svc.get_candles("SYM", 123, 1)  # type: ignore


def test_blank_timeframe_raises():
    adapter = FakeAdapter([])
    svc = MarketDataService(adapter)
    with pytest.raises(ValueError):
        svc.get_candles("SYM", "   ", 1)


def test_invalid_limit_type_raises():
    adapter = FakeAdapter([])
    svc = MarketDataService(adapter)
    with pytest.raises(ValueError):
        svc.get_candles("SYM", "1d", "100")  # type: ignore


def test_bool_limit_raises():
    adapter = FakeAdapter([])
    svc = MarketDataService(adapter)
    with pytest.raises(ValueError):
        svc.get_candles("SYM", "1d", True)  # type: ignore


def test_none_adapter_rejected():
    with pytest.raises(ValueError):
        MarketDataService(None)  # type: ignore


@pytest.mark.parametrize("bad_limit", [0, -1])
def test_non_positive_limit_raises(bad_limit):
    adapter = FakeAdapter([])
    svc = MarketDataService(adapter)
    with pytest.raises(ValueError):
        svc.get_candles("SYM", "1d", bad_limit)


def test_adapter_exception_propagates():
    adapter = FakeAdapter(to_raise=RuntimeError("adapter failure"))
    svc = MarketDataService(adapter)
    with pytest.raises(RuntimeError):
        svc.get_candles("SYM", "1d", 1)


def test_malformed_ohlc_rejected_by_candle_validation():
    rec = {"timestamp": 1, "open": "NaN", "high": 1, "low": 1, "close": 1}
    adapter = FakeAdapter([rec])
    svc = MarketDataService(adapter)
    with pytest.raises(ValueError):
        svc.get_candles("SYM", "1d", 1)


def test_no_fabrication_of_values():
    # missing volume should remain None and timestamp preserved exactly
    rec = {"timestamp": "orig-ts", "open": 1, "high": 1, "low": 1, "close": 1}
    adapter = FakeAdapter([rec])
    svc = MarketDataService(adapter)
    candles = svc.get_candles("SYM", "1d", 1)
    c = candles[0]
    assert c.timestamp == "orig-ts"
    assert c.volume is None


def test_adapter_receives_exact_parameters():
    recs = [{"timestamp": 1, "open": 1, "high": 1, "low": 1, "close": 1}]
    adapter = FakeAdapter(recs)
    svc = MarketDataService(adapter)
    svc.get_candles("MY-SYM", "5m", 50)
    assert adapter.last_called == {"symbol": "MY-SYM", "timeframe": "5m", "limit": 50}

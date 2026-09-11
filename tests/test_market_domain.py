import math
import dataclasses
import pytest
from src.platform.domain.market import Candle


def test_valid_candle_creation():
    c = Candle(timestamp=1630000000, open=100, high=110, low=90, close=105)
    assert c.open == 100.0
    assert c.high == 110.0
    assert c.low == 90.0
    assert c.close == 105.0


def test_optional_volume_is_none():
    c = Candle(timestamp="2020-01-01T00:00:00Z", open=1, high=2, low=0.5, close=1.5)
    assert c.volume is None


def test_valid_volume():
    c = Candle(timestamp=1.5, open=10, high=12, low=9, close=11, volume=1000)
    assert c.volume == 1000.0


def test_invalid_negative_volume():
    with pytest.raises(ValueError):
        Candle(timestamp=0, open=10, high=12, low=9, close=11, volume=-1)


def test_invalid_high_lower_than_low():
    with pytest.raises(ValueError):
        Candle(timestamp=0, open=100, high=80, low=90, close=85)


def test_high_lower_than_open():
    # high lower than open
    with pytest.raises(ValueError):
        Candle(timestamp=0, open=100, high=95, low=90, close=96)


def test_low_higher_than_close():
    with pytest.raises(ValueError):
        Candle(timestamp=0, open=50, high=60, low=55, close=54)


def test_non_finite_ohlc_values():
    with pytest.raises(ValueError):
        Candle(timestamp=0, open=math.inf, high=math.inf, low=math.inf, close=math.inf)


def test_immutability():
    c = Candle(timestamp=1, open=1, high=2, low=0, close=1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.open = 5


def test_to_dict_preserves_values():
    ts = "2020-01-01T00:00:00Z"
    c = Candle(timestamp=ts, open=1, high=2, low=0, close=1, volume=None)
    d = c.to_dict()
    assert d["timestamp"] == ts
    assert d["volume"] is None


def test_timestamp_not_changed():
    ts = 1234567890
    c = Candle(timestamp=ts, open=1, high=2, low=0, close=1)
    assert c.timestamp == ts


def test_bool_timestamp_rejected():
    with pytest.raises(ValueError):
        Candle(timestamp=True, open=1, high=2, low=0, close=1)


def test_blank_timestamp_string_rejected():
    with pytest.raises(ValueError):
        Candle(timestamp="  ", open=1, high=2, low=0, close=1)


def test_bool_ohlc_rejected():
    with pytest.raises(ValueError):
        Candle(timestamp=1, open=True, high=2, low=0, close=1)


def test_bool_volume_rejected():
    with pytest.raises(ValueError):
        Candle(timestamp=1, open=1, high=2, low=0, close=1, volume=True)

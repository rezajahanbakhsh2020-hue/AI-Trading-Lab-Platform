import dataclasses
import math

import pytest

from src.platform.domain.availability import Availability
from src.platform.domain.quote import Quote


def test_valid_quote_with_mid():
    quote = Quote(symbol="XAUUSD", timestamp="2026-09-11T10:00:00Z", mid=4337.7)
    assert quote.symbol == "XAUUSD"
    assert quote.timestamp == "2026-09-11T10:00:00Z"
    assert quote.mid == 4337.7
    assert quote.bid is None
    assert quote.ask is None
    assert quote.last is None
    assert quote.availability is None


def test_symbol_is_trimmed():
    quote = Quote(symbol="  EURUSD  ", timestamp=1, bid=1.1)
    assert quote.symbol == "EURUSD"


def test_zero_last_is_preserved():
    quote = Quote(symbol="EURUSD", timestamp=1, last=0)
    assert quote.last == 0.0


def test_biquote_quote_provider_normalizes_zero_last_to_none():
    from src.platform.providers.biquote_quote import BiQuoteQuoteProvider
    p = BiQuoteQuoteProvider()
    record = p._normalize_tick({
        "symbol": "XAUUSD",
        "timestamp": "2026-09-23T12:00:00Z",
        "bid": 4303.04,
        "ask": 4303.22,
        "last": 0.0,
    })
    assert record["symbol"] == "XAUUSD"
    assert record["bid"] == 4303.04
    assert record["ask"] == 4303.22
    assert "last" not in record


def test_high_low_and_change_percent_preserved():
    quote = Quote(
        symbol="XAUUSD",
        timestamp=1,
        mid=100.0,
        high=110.0,
        low=90.0,
        change_percent=-0.09,
    )
    assert quote.high == 110.0
    assert quote.low == 90.0
    assert quote.change_percent == -0.09


def test_availability_attached():
    availability = Availability(status="closed", reason="market closed")
    quote = Quote(symbol="EURUSD", timestamp=1, mid=1.08, availability=availability)
    assert quote.availability is availability
    assert quote.to_dict()["availability"]["status"] == "closed"


@pytest.mark.parametrize("symbol", ["", "   ", None, 123])
def test_invalid_symbol_raises(symbol):
    with pytest.raises(ValueError):
        Quote(symbol=symbol, timestamp=1, mid=1.0)  # type: ignore[arg-type]


def test_blank_timestamp_raises():
    with pytest.raises(ValueError):
        Quote(symbol="EURUSD", timestamp="  ", mid=1.0)


def test_no_price_fields_raises():
    with pytest.raises(ValueError):
        Quote(symbol="EURUSD", timestamp=1)


def test_non_finite_price_raises():
    with pytest.raises(ValueError):
        Quote(symbol="EURUSD", timestamp=1, mid=math.nan)


def test_high_below_low_raises():
    with pytest.raises(ValueError):
        Quote(symbol="EURUSD", timestamp=1, mid=1.0, high=1.0, low=1.1)


def test_invalid_availability_type_raises():
    with pytest.raises(ValueError):
        Quote(symbol="EURUSD", timestamp=1, mid=1.0, availability={"status": "live"})  # type: ignore[arg-type]


def test_immutability():
    quote = Quote(symbol="EURUSD", timestamp=1, mid=1.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        quote.mid = 2.0


def test_to_dict_does_not_fabricate_missing_prices():
    quote = Quote(symbol="EURUSD", timestamp="ts", bid=1.1)
    payload = quote.to_dict()
    assert payload["bid"] == 1.1
    assert payload["ask"] is None
    assert payload["mid"] is None
    assert payload["last"] is None
    assert payload["availability"] is None

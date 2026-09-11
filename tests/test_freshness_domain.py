"""Part 10 focused tests for the DataFreshness domain object."""

import dataclasses
import math

import pytest

from src.platform.domain.freshness import DataFreshness, VALID_FRESHNESS_STATUSES

@pytest.mark.parametrize("status", list(VALID_FRESHNESS_STATUSES))
def test_valid_statuses(status):
    freshness = DataFreshness(symbol="XAUUSD", timeframe="1h", status=status)
    assert freshness.status == status


def test_status_is_normalized():
    freshness = DataFreshness(symbol="XAUUSD", timeframe="1h", status=" FRESH ")
    assert freshness.status == "fresh"


@pytest.mark.parametrize("status", ["", "   ", "live", "open", 1, None])
def test_invalid_status_raises(status):
    with pytest.raises(ValueError):
        DataFreshness(symbol="XAUUSD", timeframe="1h", status=status)  # type: ignore[arg-type]


def test_symbol_and_timeframe_normalized():
    freshness = DataFreshness(symbol=" xauusd ", timeframe=" 1h ", status="fresh")
    assert freshness.symbol == "xauusd"
    assert freshness.timeframe == "1h"


@pytest.mark.parametrize("text", ["", "   "])
def test_blank_symbol_raises(text):
    with pytest.raises(ValueError):
        DataFreshness(symbol=text, timeframe="1h", status="fresh")


@pytest.mark.parametrize("text", ["", "   "])
def test_blank_timeframe_raises(text):
    with pytest.raises(ValueError):
        DataFreshness(symbol="XAUUSD", timeframe=text, status="fresh")


def test_ages_preserved_as_float():
    freshness = DataFreshness(
        symbol="XAUUSD",
        timeframe="1h",
        status="fresh",
        reference_timestamp=1000.0,
        candle_timestamp=999.0,
        quote_timestamp=990.0,
        candle_age_seconds=1.0,
        quote_age_seconds=10.0,
    )
    assert freshness.candle_age_seconds == 1.0
    assert freshness.quote_age_seconds == 10.0


@pytest.mark.parametrize("age", [-1.0, float("nan"), float("inf"), True, "5"])
def test_invalid_age_raises(age):
    with pytest.raises(ValueError):
        DataFreshness(
            symbol="XAUUSD",
            timeframe="1h",
            status="fresh",
            candle_age_seconds=age,
        )  # type: ignore[arg-type]


def test_missing_fields_remain_none():
    freshness = DataFreshness(symbol="XAUUSD", timeframe="1h", status="unknown")
    assert freshness.reference_timestamp is None
    assert freshness.candle_timestamp is None
    assert freshness.quote_timestamp is None
    assert freshness.candle_age_seconds is None
    assert freshness.quote_age_seconds is None
    assert freshness.reason is None


@pytest.mark.parametrize("timestamp", ["", "   ", True, float("nan")])
def test_invalid_timestamp_raises(timestamp):
    with pytest.raises(ValueError):
        DataFreshness(
            symbol="XAUUSD",
            timeframe="1h",
            status="fresh",
            reference_timestamp=timestamp,
        )


def test_reason_must_be_non_blank():
    with pytest.raises(ValueError):
        DataFreshness(symbol="XAUUSD", timeframe="1h", status="stale", reason="   ")


def test_to_dict_shape():
    freshness = DataFreshness(
        symbol="XAUUSD",
        timeframe="1h",
        status="stale",
        reference_timestamp=1000.0,
        candle_timestamp=999.0,
        candle_age_seconds=1.0,
        reason="behind",
    )
    payload = freshness.to_dict()
    assert payload["symbol"] == "XAUUSD"
    assert payload["timeframe"] == "1h"
    assert payload["status"] == "stale"
    assert payload["reference_timestamp"] == 1000.0
    assert payload["candle_timestamp"] == 999.0
    assert payload["candle_age_seconds"] == 1.0
    assert payload["quote_age_seconds"] is None
    assert payload["reason"] == "behind"


def test_immutability():
    freshness = DataFreshness(symbol="XAUUSD", timeframe="1h", status="fresh")
    with pytest.raises(dataclasses.FrozenInstanceError):
        freshness.status = "stale"


def test_exported_from_domain():
    from src.platform.domain import DataFreshness as Exported
    assert Exported is DataFreshness

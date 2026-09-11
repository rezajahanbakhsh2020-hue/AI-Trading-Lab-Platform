"""Part 10 focused tests for the ProviderMonitor application service."""

import pytest

from src.platform.domain import Availability
from src.platform.domain.freshness import DataFreshness
from src.platform.domain.market import Candle
from src.platform.domain.quote import Quote
from src.platform.integrations.lab import LabArtifactSource
from src.platform.services import (
    CandleOperationResult,
    LabArtifactService,
    ProviderAccess,
    ProviderMonitor,
    ProviderOperations,
    ProviderRegistry,
    QuoteOperationResult,
)


class FakeOperations(ProviderOperations):
    """ProviderOperations double recording explicit fetches."""

    def __init__(self, candles=None, quote=None, to_raise=None):
        super().__init__(ProviderAccess(ProviderRegistry()))
        self.candles = candles if candles is not None else []
        self.quote = quote
        self.to_raise = to_raise
        self.fetch_candles_calls = 0
        self.fetch_quote_calls = 0

    def fetch_candles(self, provider_id, symbol, timeframe, limit):
        self.fetch_candles_calls += 1
        self.last_candles_args = (provider_id, symbol, timeframe, limit)
        if self.to_raise is not None:
            raise self.to_raise
        return CandleOperationResult(
            provider_id=provider_id,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            candles=self.candles,
        )

    def fetch_quote(self, provider_id, symbol):
        self.fetch_quote_calls += 1
        self.last_quote_args = (provider_id, symbol)
        if self.to_raise is not None:
            raise self.to_raise
        return QuoteOperationResult(
            provider_id=provider_id,
            symbol=symbol,
            quote=self.quote,
        )


class _FakeSource(LabArtifactSource):
    def connect(self):
        return None

    def fetch_signal(self, symbol, timeframe):
        return None

    def fetch_trade_setup(self, symbol, timeframe):
        return None

    def fetch_stability(self, strategy_name):
        return None

    def close(self):
        return None

    def describe(self):
        return {"name": "fake-source"}


def _candle_at(timestamp, index=0):
    return Candle(
        timestamp=timestamp,
        open=1.0,
        high=1.2,
        low=0.9,
        close=1.1,
        volume=100.0,
    )


def _quote_at(timestamp, status="live"):
    return Quote(
        symbol="XAUUSD",
        timestamp=timestamp,
        mid=1.0,
        availability=Availability(status=status),
    )


def _monitor(ops=None, lab=None, clock=None):
    if ops is None:
        ops = FakeOperations()
    return ProviderMonitor(operations=ops, lab=lab, clock=clock), ops


def test_requires_operations():
    with pytest.raises(ValueError):
        ProviderMonitor(None)


def test_rejects_non_operations():
    with pytest.raises(ValueError):
        ProviderMonitor(object())  # type: ignore


def test_rejects_invalid_lab():
    with pytest.raises(ValueError):
        ProviderMonitor(FakeOperations(), lab=object())  # type: ignore


def test_rejects_invalid_clock():
    with pytest.raises(ValueError):
        ProviderMonitor(FakeOperations(), clock=42)  # type: ignore


def test_fresh_when_both_ages_within_threshold():
    ops = FakeOperations(
        candles=[_candle_at(995.0)],
        quote=_quote_at(990.0),
    )
    svc, _ = _monitor(ops)
    snapshot = svc.monitor(
        symbol="XAUUSD",
        timeframe="1h",
        market_data_provider_id="md_one",
        quote_provider_id="qt_one",
        reference=1000.0,
    )
    assert isinstance(snapshot.freshness, DataFreshness)
    assert snapshot.freshness.status == "fresh"
    assert snapshot.freshness.candle_age_seconds == 5.0
    assert snapshot.freshness.quote_age_seconds == 10.0
    assert snapshot.freshness.reference_timestamp == 1000.0
    assert snapshot.candle_count == 1
    assert snapshot.quote_status == "live"
    assert snapshot.quote_provider_id == "qt_one"
    assert snapshot.market_data_provider_id == "md_one"


def test_stale_when_oldest_age_exceeds_threshold():
    ops = FakeOperations(
        candles=[_candle_at(900.0)],
        quote=_quote_at(995.0),
    )
    svc, _ = _monitor(ops)
    snapshot = svc.monitor(
        "XAUUSD",
        "1h",
        market_data_provider_id="md_one",
        quote_provider_id="qt_one",
        reference=1000.0,
    )
    assert snapshot.freshness.status == "stale"
    assert snapshot.freshness.candle_age_seconds == 100.0
    assert snapshot.freshness.quote_age_seconds == 5.0


def test_exactly_at_threshold_is_fresh():
    ops = FakeOperations(candles=[_candle_at(940.0)])
    svc, _ = _monitor(ops)
    snapshot = svc.monitor("XAUUSD", "1h", market_data_provider_id="md_one", reference=1000.0, max_age_seconds=60.0)
    assert snapshot.freshness.status == "fresh"
    assert snapshot.freshness.candle_age_seconds == 60.0


def test_unknown_when_no_age_computable():
    ops = FakeOperations(
        candles=[_candle_at("not-a-time")],
        quote=_quote_at("also-not-a-time"),
    )
    svc, _ = _monitor(ops)
    snapshot = svc.monitor(
        "XAUUSD",
        "1h",
        market_data_provider_id="md_one",
        quote_provider_id="qt_one",
        reference=1000.0,
    )
    assert snapshot.freshness.status == "unknown"
    assert snapshot.freshness.candle_age_seconds is None
    assert snapshot.freshness.quote_age_seconds is None


def test_unavailable_when_quote_reports_unavailable():
    ops = FakeOperations(
        candles=[_candle_at(995.0)],
        quote=_quote_at(990.0, status="unavailable"),
    )
    svc, _ = _monitor(ops)
    snapshot = svc.monitor(
        "XAUUSD",
        "1h",
        market_data_provider_id="md_one",
        quote_provider_id="qt_one",
        reference=1000.0,
    )
    assert snapshot.freshness.status == "unavailable"
    assert snapshot.freshness.reason is not None


def test_omitted_quote_leaves_quote_age_none_and_keeps_freshness():
    ops = FakeOperations(candles=[_candle_at(995.0)])
    svc, _ = _monitor(ops)
    snapshot = svc.monitor(
        "XAUUSD",
        "1h",
        market_data_provider_id="md_one",
        reference=1000.0,
    )
    assert snapshot.quote_provider_id is None
    assert snapshot.freshness.quote_timestamp is None
    assert snapshot.freshness.quote_age_seconds is None
    assert snapshot.freshness.status == "fresh"


def test_iso_reference_parsed():
    ops = FakeOperations(candles=[_candle_at("2026-09-11T10:00:00Z")])
    reference = "2026-09-11T11:00:00Z"
    svc, _ = _monitor(ops)
    snapshot = svc.monitor("XAUUSD", "1h", market_data_provider_id="md_one", reference=reference)
    assert snapshot.freshness.candle_age_seconds == 3600.0
    assert snapshot.freshness.status == "stale"


def test_clock_used_when_reference_omitted():
    calls = []
    def clock():
        calls.append(1)
        return 1000.0
    ops = FakeOperations(candles=[_candle_at(999.0)])
    svc, _ = _monitor(ops, clock=clock)
    snapshot = svc.monitor("XAUUSD", "1h", market_data_provider_id="md_one")
    assert calls == [1]
    assert snapshot.freshness.candle_age_seconds == 1.0
    assert snapshot.freshness.reference_timestamp == 1000.0


def test_invalid_symbol_rejected_before_fetch():
    ops = FakeOperations()
    svc, _ = _monitor(ops)
    with pytest.raises(ValueError):
        svc.monitor(" ", "1h", market_data_provider_id="md_one")
    assert ops.fetch_candles_calls == 0


def test_invalid_timeframe_rejected_before_fetch():
    ops = FakeOperations()
    svc, _ = _monitor(ops)
    with pytest.raises(ValueError):
        svc.monitor("XAUUSD", "   ", market_data_provider_id="md_one")
    assert ops.fetch_candles_calls == 0


def test_invalid_max_age_rejected_before_fetch():
    ops = FakeOperations()
    svc, _ = _monitor(ops)
    with pytest.raises(ValueError):
        svc.monitor("XAUUSD", "1h", market_data_provider_id="md_one", max_age_seconds=-1)
    assert ops.fetch_candles_calls == 0


def test_candle_failure_propagates():
    ops = FakeOperations(to_raise=RuntimeError("candle boom"))
    svc, _ = _monitor(ops)
    with pytest.raises(RuntimeError, match="candle boom"):
        svc.monitor("XAUUSD", "1h", market_data_provider_id="md_one")


def test_quote_failure_propagates():
    ops = FakeOperations(candles=[_candle_at(995.0)], to_raise=RuntimeError("quote boom"))
    svc, _ = _monitor(ops)
    with pytest.raises(RuntimeError, match="quote boom"):
        svc.monitor(
            "XAUUSD",
            "1h",
            market_data_provider_id="md_one",
            quote_provider_id="qt_one",
        )


def test_lab_not_required():
    svc, _ = _monitor()
    snapshot = svc.monitor("XAUUSD", "1h", market_data_provider_id="md_one", reference=1000.0)
    assert snapshot.freshness is not None


def test_latest_candle_used_for_age():
    ops = FakeOperations(candles=[_candle_at(950.0), _candle_at(999.0)])
    svc, _ = _monitor(ops)
    snapshot = svc.monitor("XAUUSD", "1h", market_data_provider_id="md_one", reference=1000.0)
    assert snapshot.freshness.candle_age_seconds == 1.0


def test_snapshot_to_dict_shape():
    ops = FakeOperations(candles=[_candle_at(995.0)], quote=_quote_at(990.0))
    svc, _ = _monitor(ops)
    snapshot = svc.monitor(
        "XAUUSD",
        "1h",
        market_data_provider_id="md_one",
        quote_provider_id="qt_one",
        reference=1000.0,
    )
    data = snapshot.to_dict()
    assert data["symbol"] == "XAUUSD"
    assert data["timeframe"] == "1h"
    assert data["market_data_provider_id"] == "md_one"
    assert data["quote_provider_id"] == "qt_one"
    assert data["candle_count"] == 1
    assert data["quote_status"] == "live"
    assert data["freshness"]["status"] == "fresh"
    assert data["freshness"]["candle_age_seconds"] == 5.0


def test_exported_from_services():
    from src.platform.services import ProviderMonitor as Exported
    assert Exported is ProviderMonitor

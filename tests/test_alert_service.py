"""Part 11 focused tests for the alerts application service."""

import pytest

from src.platform.domain import Availability
from src.platform.domain.alert import MarketAlert
from src.platform.domain.freshness import DataFreshness
from src.platform.domain.market import Candle
from src.platform.domain.quote import Quote
from src.platform.integrations.lab import LabArtifactSource
from src.platform.services import (
    CandleOperationResult,
    ProviderAccess,
    ProviderMonitor,
    ProviderOperations,
    ProviderRegistry,
    QuoteOperationResult,
)
from src.platform.services.alert_service import AlertService


class FakeOperations(ProviderOperations):
    def __init__(self, candles=None, quote=None):
        super().__init__(ProviderAccess(ProviderRegistry()))
        self.candles = candles if candles is not None else []
        self.quote = quote
        self.fetch_candles_calls = 0
        self.fetch_quote_calls = 0

    def fetch_candles(self, provider_id, symbol, timeframe, limit):
        self.fetch_candles_calls += 1
        return CandleOperationResult(
            provider_id=provider_id,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            candles=self.candles,
        )

    def fetch_quote(self, provider_id, symbol):
        self.fetch_quote_calls += 1
        return QuoteOperationResult(
            provider_id=provider_id,
            symbol=symbol,
            quote=self.quote,
        )


class _FakeSource(LabArtifactSource):
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


def _candle_at(timestamp):
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


def _monitor(ops=None):
    if ops is None:
        ops = FakeOperations()
    return ProviderMonitor(operations=ops)


def _svc(ops=None, created_at=1700000000.0, clock=None):
    monitor = _monitor(ops)
    if clock is not None:
        return AlertService(monitor, created_at=created_at, clock=clock)
    return AlertService(monitor, created_at=created_at)


def _ref():
    return 1700000000.0


def _evaluate(svc, include_healthy=False):
    return svc.evaluate(
        symbol="XAUUSD",
        timeframe="1h",
        market_data_provider_id="md_one",
        quote_provider_id="qt_one",
        max_age_seconds=60.0,
        reference=_ref(),
        include_healthy=include_healthy,
    )


def test_requires_monitor():
    with pytest.raises(ValueError):
        AlertService(None)


def test_rejects_non_monitor():
    with pytest.raises(ValueError):
        AlertService(object())  # type: ignore


def test_rejects_invalid_clock():
    with pytest.raises(ValueError):
        AlertService(_monitor(), clock=42)  # type: ignore


def test_fresh_produces_no_alert():
    ops = FakeOperations(
        candles=[_candle_at(1699999995.0)],
        quote=_quote_at(1699999995.0),
    )
    alert = _evaluate(_svc(ops))
    assert alert is None


def test_fresh_include_healthy_produces_info_alert():
    ops = FakeOperations(
        candles=[_candle_at(1699999995.0)],
        quote=_quote_at(1699999995.0),
    )
    alert = _evaluate(_svc(ops), include_healthy=True)
    assert isinstance(alert, MarketAlert)
    assert alert.id == "freshness-ok"
    assert alert.severity == "info"
    assert alert.kind == "freshness"
    assert alert.status == "active"


def test_stale_produces_warning():
    ops = FakeOperations(
        candles=[_candle_at(1699999900.0)],
        quote=_quote_at(1699999900.0),
    )
    alert = _evaluate(_svc(ops))
    assert isinstance(alert, MarketAlert)
    assert alert.id == "freshness-stale"
    assert alert.severity == "warning"
    assert "Market data is stale" in alert.message
    assert alert.details["candle_count"] == 1
    assert alert.details["freshness"]["status"] == "stale"


def test_unavailable_produces_critical():
    ops = FakeOperations(
        candles=[],
        quote=_quote_at(1699999995.0, status="unavailable"),
    )
    alert = _evaluate(_svc(ops))
    assert isinstance(alert, MarketAlert)
    assert alert.id == "freshness-unavailable"
    assert alert.severity == "critical"
    assert alert.details["freshness"]["status"] == "unavailable"


def test_unknown_produces_info():
    ops = FakeOperations(candles=[], quote=None)
    svc = _svc(ops)
    alert = svc.evaluate(
        symbol="XAUUSD",
        timeframe="1h",
        market_data_provider_id="md_one",
        quote_provider_id=None,
        max_age_seconds=60.0,
        reference=_ref(),
    )
    assert isinstance(alert, MarketAlert)
    assert alert.id == "freshness-unknown"
    assert alert.severity == "info"


def test_bad_include_healthy_rejected():
    with pytest.raises(ValueError):
        _evaluate(_svc(), include_healthy="yes")  # type: ignore

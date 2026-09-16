"""Part 11 focused tests for the alerts application service."""

import pytest

from src.platform.domain import Availability
from src.platform.domain.alert import AlertRule, MarketAlert
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
    svc = AlertService(None)
    with pytest.raises(ValueError):
        _evaluate(svc)


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


def test_evaluate_rule_price_above():
    svc = AlertService()
    rule = AlertRule(
        rule_id="r1",
        kind="price",
        symbol="XAUUSD",
        condition_type="price_above",
        threshold=2700.0,
    )
    alert = svc.evaluate_rule(rule, current_price=2705.5)
    assert alert is not None
    assert alert.kind == "price"
    assert alert.severity == "warning"
    assert "2705.50" in alert.message


def test_evaluate_rule_price_below_not_triggered():
    svc = AlertService()
    rule = AlertRule(
        rule_id="r2",
        kind="price",
        symbol="XAUUSD",
        condition_type="price_below",
        threshold=2600.0,
    )
    alert = svc.evaluate_rule(rule, current_price=2650.0)
    assert alert is None


def test_evaluate_rule_signal_action():
    svc = AlertService()
    rule = AlertRule(
        rule_id="r3",
        kind="signal",
        symbol="XAUUSD",
        condition_type="signal_action",
        expected_value="BUY",
    )
    alert = svc.evaluate_rule(rule, signal_action="BUY")
    assert alert is not None
    assert alert.kind == "signal"
    assert alert.symbol == "XAUUSD"


def test_evaluate_rule_provider_disconnect():
    svc = AlertService()
    rule = AlertRule(
        rule_id="r4",
        kind="provider",
        symbol="XAUUSD",
        condition_type="provider_disconnect",
    )
    alert = svc.evaluate_rule(rule, provider_connected=False)
    assert alert is not None
    assert alert.kind == "provider"
    assert alert.severity == "critical"


def test_acknowledge_and_resolve_alert_lifecycle():
    svc = AlertService()
    rule = AlertRule(
        rule_id="r1",
        kind="price",
        symbol="XAUUSD",
        condition_type="price_above",
        threshold=2700.0,
    )
    alert = svc.evaluate_rule(rule, current_price=2710.0)
    assert alert is not None
    assert alert.status == "active"

    ack_alert = svc.acknowledge_alert(alert)
    assert ack_alert.status == "acknowledged"

    res_alert = svc.resolve_alert(ack_alert)
    assert res_alert.status == "resolved"

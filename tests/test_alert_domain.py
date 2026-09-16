"""Unit tests for alert domain models (AlertRule & MarketAlert)."""

import pytest
from src.platform.domain.alert import AlertRule, MarketAlert, VALID_ALERT_KINDS


def test_alert_rule_validation():
    rule = AlertRule(
        rule_id="r101",
        kind="price",
        symbol="XAUUSD",
        condition_type="price_above",
        threshold=2700.0,
        timeframe="1h",
        enabled=True,
    )
    assert rule.rule_id == "r101"
    assert rule.kind == "price"
    assert rule.symbol == "XAUUSD"
    assert rule.condition_type == "price_above"
    assert rule.threshold == 2700.0
    assert rule.to_dict()["rule_id"] == "r101"


def test_alert_rule_invalid_kind():
    with pytest.raises(ValueError):
        AlertRule(
            rule_id="r1",
            kind="invalid_kind",
            symbol="XAUUSD",
            condition_type="price_above",
        )


def test_alert_rule_invalid_condition_type():
    with pytest.raises(ValueError):
        AlertRule(
            rule_id="r1",
            kind="price",
            symbol="XAUUSD",
            condition_type="unknown_condition",
        )


def test_market_alert_kinds():
    for kind in VALID_ALERT_KINDS:
        alert = MarketAlert(
            id=f"alert-{kind}",
            kind=kind,
            severity="warning",
            status="active",
            message=f"Test alert for {kind}",
            symbol="XAUUSD",
            timeframe="1h",
            created_at=1700000000,
        )
        assert alert.kind == kind
        assert alert.to_dict()["kind"] == kind

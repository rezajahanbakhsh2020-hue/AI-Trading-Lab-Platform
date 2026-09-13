"""Part 15 focused tests for full autonomous authorization domain and application service."""

import pytest

from src.platform.domain.autonomous_authorization import (
    AUTHORIZATION_STATUS_AUTHORIZED,
    AUTHORIZATION_STATUS_REJECTED,
    AutonomousAuthorization,
)
from src.platform.domain.provider_readiness import (
    PROVIDER_STATUS_NOT_READY,
    PROVIDER_STATUS_READY,
    ProviderReadiness,
)
from src.platform.domain.provider_selection import (
    SELECTION_STATUS_NOT_AVAILABLE,
    SELECTION_STATUS_SELECTED,
    ProviderSelection,
)
from src.platform.domain.readiness import Readiness
from src.platform.domain.stability import Stability
from src.platform.domain.strategy_result import StrategyResult
from src.platform.domain.trade_readiness import TradeReadiness
from src.platform.domain.trade_setup import TradeSetup
from src.platform.domain.trade_signal import TradeSignal
from src.platform.services.autonomous_authorization import (
    REASON_AUTHORIZED,
    REASON_INSUFFICIENT_RR,
    REASON_LEVELS_INSANE,
    REASON_PROVIDER_NOT_SELECTED,
    REASON_PROVIDER_REQUIRED,
    REASON_SIGNAL_NOT_TRADABLE,
    AutonomousAuthorizationService,
)
from src.platform.services.provider_registry import CATEGORY_MARKET_DATA
from src.platform.services.trade_signal import TradeSignalService


def _buy_setup(symbol="XAUUSD", entry=2000.0, sl=1990.0, tp1=2020.0, tp2=2030.0, tp3=2040.0, timestamp=10.0):
    return TradeSetup(
        symbol=symbol,
        entry_price=entry,
        stop_loss=sl,
        take_profit_1=tp1,
        take_profit_2=tp2,
        take_profit_3=tp3,
        timestamp=timestamp,
        direction="buy",
    )


def _strategy_result(
    action="buy",
    approved=True,
    risk_level="low",
    score=0.8,
    setup=None,
    timestamp=10.0,
):
    if setup is None and action == "buy":
        setup = _buy_setup(timestamp=timestamp)
    return StrategyResult(
        strategy_name="TestStrategy",
        timestamp=timestamp,
        proposed_action=action,
        stability=Stability(score=score, risk_level=risk_level),
        readiness=Readiness(approved=approved, timestamp=timestamp),
        trade_setup=setup,
    )


def _tradable_signal(timestamp=10.0):
    svc = TradeSignalService()
    return svc.generate(_strategy_result(action="buy", timestamp=timestamp))


def _non_tradable_signal(timestamp=10.0):
    svc = TradeSignalService()
    return svc.generate(_strategy_result(action="hold", timestamp=timestamp))


def _selected_provider(provider_id="md1", category=CATEGORY_MARKET_DATA):
    readiness = ProviderReadiness(
        provider_id=provider_id,
        category=category,
        status=PROVIDER_STATUS_READY,
        reason="provider operational",
    )
    return ProviderSelection(
        category=category,
        status=SELECTION_STATUS_SELECTED,
        reason=f"selected ready provider '{provider_id}'",
        selected_provider_id=provider_id,
        readiness=readiness,
        evaluated_readiness=(readiness,),
    )


def _unselected_provider(category=CATEGORY_MARKET_DATA):
    readiness = ProviderReadiness(
        provider_id="md_bad",
        category=category,
        status=PROVIDER_STATUS_NOT_READY,
        reason="unhealthy",
    )
    return ProviderSelection(
        category=category,
        status=SELECTION_STATUS_NOT_AVAILABLE,
        reason="no ready provider available",
        selected_provider_id=None,
        readiness=None,
        evaluated_readiness=(readiness,),
    )


def _sane_trade_readiness(direction="buy", entry=2000.0, sl=1990.0, tp1=2020.0, rr=2.0):
    return TradeReadiness(
        symbol="XAUUSD",
        timeframe="1h",
        direction=direction,
        entry_price=entry,
        stop_loss=sl,
        take_profit_1=tp1,
        take_profit_2=2030.0,
        take_profit_3=2040.0,
        current_price=2000.0,
        risk_reward_to_tp1=rr,
        levels_are_sane=True,
    )


def _insane_trade_readiness():
    return TradeReadiness(
        symbol="XAUUSD",
        timeframe="1h",
        direction="buy",
        entry_price=2000.0,
        stop_loss=2010.0,  # SL on wrong side for buy
        take_profit_1=2020.0,
        take_profit_2=2030.0,
        take_profit_3=2040.0,
        current_price=2000.0,
        risk_reward_to_tp1=None,
        levels_are_sane=False,
    )


# --- Domain Model Tests ---

def test_autonomous_authorization_domain_success():
    sig = _tradable_signal()
    prov = _selected_provider()
    tr = _sane_trade_readiness()

    auth = AutonomousAuthorization(
        status=AUTHORIZATION_STATUS_AUTHORIZED,
        reason=REASON_AUTHORIZED,
        timestamp=10.0,
        trade_signal=sig,
        provider_selection=prov,
        trade_readiness=tr,
    )

    assert auth.status == AUTHORIZATION_STATUS_AUTHORIZED
    assert auth.is_authorized is True
    assert auth.reason == REASON_AUTHORIZED
    assert auth.timestamp == 10.0
    assert auth.trade_signal == sig
    assert auth.provider_selection == prov
    assert auth.trade_readiness == tr

    d = auth.to_dict()
    assert d["status"] == AUTHORIZATION_STATUS_AUTHORIZED
    assert d["is_authorized"] is True
    assert d["reason"] == REASON_AUTHORIZED
    assert d["trade_signal"]["tradable"] is True
    assert d["provider_selection"]["status"] == SELECTION_STATUS_SELECTED
    assert d["trade_readiness"]["levels_are_sane"] is True


def test_autonomous_authorization_domain_immutability_and_validation():
    sig = _tradable_signal()
    auth = AutonomousAuthorization(
        status=AUTHORIZATION_STATUS_AUTHORIZED,
        reason="authorized",
        timestamp=10.0,
        trade_signal=sig,
    )

    with pytest.raises((AttributeError, TypeError)):
        auth.status = AUTHORIZATION_STATUS_REJECTED  # type: ignore

    with pytest.raises(ValueError):
        AutonomousAuthorization(
            status="INVALID_STATUS",
            reason="test",
            timestamp=10.0,
            trade_signal=sig,
        )

    with pytest.raises(ValueError):
        AutonomousAuthorization(
            status=AUTHORIZATION_STATUS_AUTHORIZED,
            reason="",
            timestamp=10.0,
            trade_signal=sig,
        )

    with pytest.raises(ValueError):
        AutonomousAuthorization(
            status=AUTHORIZATION_STATUS_AUTHORIZED,
            reason="test",
            timestamp=-1.0,
            trade_signal=sig,
        )

    with pytest.raises(ValueError):
        AutonomousAuthorization(
            status=AUTHORIZATION_STATUS_AUTHORIZED,
            reason="test",
            timestamp=10.0,
            trade_signal="not_a_trade_signal",  # type: ignore
        )


# --- Application Service Tests ---

def test_service_authorize_success():
    svc = AutonomousAuthorizationService()
    sig = _tradable_signal(timestamp=10.0)
    prov = _selected_provider()
    tr = _sane_trade_readiness(rr=2.0)

    auth = svc.authorize(
        trade_signal=sig,
        provider_selection=prov,
        trade_readiness=tr,
        min_risk_reward_to_tp1=1.5,
        require_selected_provider=True,
    )

    assert auth.status == AUTHORIZATION_STATUS_AUTHORIZED
    assert auth.is_authorized is True
    assert auth.reason == REASON_AUTHORIZED
    assert auth.timestamp == 10.0


def test_service_rejects_non_tradable_signal():
    svc = AutonomousAuthorizationService()
    sig = _non_tradable_signal(timestamp=10.0)

    auth = svc.authorize(trade_signal=sig)

    assert auth.status == AUTHORIZATION_STATUS_REJECTED
    assert auth.is_authorized is False
    assert REASON_SIGNAL_NOT_TRADABLE in auth.reason


def test_service_rejects_missing_required_provider():
    svc = AutonomousAuthorizationService()
    sig = _tradable_signal()

    auth = svc.authorize(trade_signal=sig, require_selected_provider=True)

    assert auth.status == AUTHORIZATION_STATUS_REJECTED
    assert auth.is_authorized is False
    assert auth.reason == REASON_PROVIDER_REQUIRED


def test_service_rejects_unselected_provider():
    svc = AutonomousAuthorizationService()
    sig = _tradable_signal()
    unsel_prov = _unselected_provider()

    auth = svc.authorize(trade_signal=sig, provider_selection=unsel_prov)

    assert auth.status == AUTHORIZATION_STATUS_REJECTED
    assert auth.is_authorized is False
    assert REASON_PROVIDER_NOT_SELECTED in auth.reason


def test_service_rejects_insane_trade_readiness_levels():
    svc = AutonomousAuthorizationService()
    sig = _tradable_signal()
    tr_insane = _insane_trade_readiness()

    auth = svc.authorize(trade_signal=sig, trade_readiness=tr_insane)

    assert auth.status == AUTHORIZATION_STATUS_REJECTED
    assert auth.is_authorized is False
    assert auth.reason == REASON_LEVELS_INSANE


def test_service_rejects_insufficient_risk_reward():
    svc = AutonomousAuthorizationService()
    sig = _tradable_signal()
    tr_low_rr = _sane_trade_readiness(rr=1.0)

    auth = svc.authorize(
        trade_signal=sig,
        trade_readiness=tr_low_rr,
        min_risk_reward_to_tp1=1.5,
    )

    assert auth.status == AUTHORIZATION_STATUS_REJECTED
    assert auth.is_authorized is False
    assert REASON_INSUFFICIENT_RR in auth.reason


def test_service_invalid_input_validation():
    svc = AutonomousAuthorizationService()
    sig = _tradable_signal()

    with pytest.raises(ValueError):
        svc.authorize(trade_signal="not_a_signal")  # type: ignore

    with pytest.raises(ValueError):
        svc.authorize(trade_signal=sig, timestamp=-5.0)

    with pytest.raises(ValueError):
        svc.authorize(trade_signal=sig, min_risk_reward_to_tp1=-1.0)

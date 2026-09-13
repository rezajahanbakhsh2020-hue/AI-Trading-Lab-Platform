"""Focused tests for Part 18 StrategyValidationService and ValidatedStrategyState."""

import pytest

from src.platform.domain.backtest import BacktestResult
from src.platform.domain.stability import Stability
from src.platform.domain.trade_setup import TradeSetup
from src.platform.domain.validated_strategy import (
    STRATEGY_STATUS_REJECTED,
    STRATEGY_STATUS_UNVALIDATED,
    STRATEGY_STATUS_VALIDATED,
    ValidatedStrategyState,
)
from src.platform.services.strategy_validation import (
    REASON_HIGH_DRAWDOWN,
    REASON_LOW_WIN_RATE,
    REASON_NO_BACKTEST,
    REASON_NO_TRADES,
    REASON_UNSTABLE_RISK,
    REASON_VALIDATED,
    StrategyValidationService,
)


def _backtest(
    strategy_name="Momentum",
    symbol="XAUUSD",
    timeframe="1h",
    trades=20,
    win_rate=0.65,
    pf=1.8,
    drawdown=0.08,
    profit=1500.0,
    risk_level="low",
    score=0.8,
):
    return BacktestResult(
        strategy_name=strategy_name,
        symbol=symbol,
        timeframe=timeframe,
        total_trades=trades,
        win_rate=win_rate,
        profit_factor=pf,
        max_drawdown=drawdown,
        net_profit=profit,
        stability=Stability(score=score, risk_level=risk_level),
    )


def _setup():
    return TradeSetup(
        symbol="XAUUSD",
        entry_price=2000.0,
        stop_loss=1990.0,
        take_profit_1=2020.0,
        take_profit_2=2030.0,
        take_profit_3=2040.0,
        timestamp=10.0,
        direction="buy",
    )


def test_validation_success():
    svc = StrategyValidationService()
    bt = _backtest()
    setup = _setup()

    state = svc.validate(strategy_name="Momentum", backtest_result=bt, trade_setup=setup)

    assert isinstance(state, ValidatedStrategyState)
    assert state.status == STRATEGY_STATUS_VALIDATED
    assert state.is_validated is True
    assert state.reason == REASON_VALIDATED
    assert state.backtest_result == bt
    assert state.trade_setup == setup


def test_validation_conversion_to_strategy_result():
    svc = StrategyValidationService()
    bt = _backtest()
    setup = _setup()

    state = svc.validate(strategy_name="Momentum", backtest_result=bt, trade_setup=setup)
    res = state.to_strategy_result(proposed_action="buy")

    assert res.strategy_name == "Momentum"
    assert res.proposed_action == "buy"
    assert res.readiness.approved is True
    assert res.trade_setup == setup


def test_validation_missing_backtest_yields_unvalidated():
    svc = StrategyValidationService()

    state = svc.validate(strategy_name="Momentum", backtest_result=None)

    assert state.status == STRATEGY_STATUS_UNVALIDATED
    assert state.is_validated is False
    assert state.reason == REASON_NO_BACKTEST


def test_validation_rejected_insufficient_trades():
    svc = StrategyValidationService()
    bt = _backtest(trades=3)

    state = svc.validate(strategy_name="Momentum", backtest_result=bt, min_trades=5)

    assert state.status == STRATEGY_STATUS_REJECTED
    assert REASON_NO_TRADES in state.reason


def test_validation_rejected_high_drawdown():
    svc = StrategyValidationService()
    bt = _backtest(drawdown=0.30)

    state = svc.validate(strategy_name="Momentum", backtest_result=bt, max_drawdown=0.20)

    assert state.status == STRATEGY_STATUS_REJECTED
    assert REASON_HIGH_DRAWDOWN in state.reason


def test_validation_rejected_low_win_rate():
    svc = StrategyValidationService()
    bt = _backtest(win_rate=0.40)

    state = svc.validate(strategy_name="Momentum", backtest_result=bt, min_win_rate=0.50)

    assert state.status == STRATEGY_STATUS_REJECTED
    assert REASON_LOW_WIN_RATE in state.reason


def test_validation_rejected_unstable_risk():
    svc = StrategyValidationService()
    bt = _backtest(risk_level="critical")

    state = svc.validate(strategy_name="Momentum", backtest_result=bt, allowed_risk_levels=("low", "medium"))

    assert state.status == STRATEGY_STATUS_REJECTED
    assert REASON_UNSTABLE_RISK in state.reason


def test_validated_strategy_state_to_dict():
    state = ValidatedStrategyState(
        strategy_name="Momentum",
        status=STRATEGY_STATUS_VALIDATED,
        reason=REASON_VALIDATED,
        timestamp=10.0,
    )
    d = state.to_dict()
    assert d["strategy_name"] == "Momentum"
    assert d["status"] == STRATEGY_STATUS_VALIDATED
    assert d["is_validated"] is True

import dataclasses

import pytest

from src.platform.domain.readiness import Readiness
from src.platform.domain.stability import Stability
from src.platform.domain.strategy_result import StrategyResult
from src.platform.domain.trade_setup import TradeSetup


def _stability(risk_level="low", score=0.8):
    return Stability(score=score, risk_level=risk_level)


def _readiness(approved=True, reason=None):
    return Readiness(approved=approved, reason=reason, timestamp=1)


def _buy_setup():
    return TradeSetup(
        symbol="XAUUSD",
        entry_price=2000.0,
        stop_loss=1990.0,
        take_profit_1=2020.0,
        take_profit_2=2030.0,
        take_profit_3=2040.0,
        timestamp=1,
        direction="buy",
    )


def test_valid_strategy_result():
    result = StrategyResult(
        strategy_name="Momentum",
        timestamp=10,
        proposed_action="buy",
        stability=_stability(),
        readiness=_readiness(),
        trade_setup=_buy_setup(),
    )
    assert result.strategy_name == "Momentum"
    assert result.proposed_action == "buy"
    assert result.trade_setup.entry_price == 2000.0


def test_action_and_name_are_normalized():
    result = StrategyResult(
        strategy_name="  Momentum  ",
        timestamp=10,
        proposed_action=" NO_SIGNAL ",
        stability=_stability(),
        readiness=_readiness(approved=False, reason="none"),
    )
    assert result.strategy_name == "Momentum"
    assert result.proposed_action == "no-signal"


@pytest.mark.parametrize("strategy_name", ["", "   ", None, 1])
def test_invalid_strategy_name(strategy_name):
    with pytest.raises(ValueError):
        StrategyResult(
            strategy_name=strategy_name,  # type: ignore[arg-type]
            timestamp=1,
            proposed_action="buy",
            stability=_stability(),
            readiness=_readiness(),
        )


@pytest.mark.parametrize("action", ["", "long", "short", None])
def test_invalid_proposed_action(action):
    with pytest.raises(ValueError):
        StrategyResult(
            strategy_name="S",
            timestamp=1,
            proposed_action=action,  # type: ignore[arg-type]
            stability=_stability(),
            readiness=_readiness(),
        )


def test_invalid_stability_type():
    with pytest.raises(ValueError):
        StrategyResult(
            strategy_name="S",
            timestamp=1,
            proposed_action="buy",
            stability={"score": 0.8},  # type: ignore[arg-type]
            readiness=_readiness(),
        )


def test_invalid_readiness_type():
    with pytest.raises(ValueError):
        StrategyResult(
            strategy_name="S",
            timestamp=1,
            proposed_action="buy",
            stability=_stability(),
            readiness=True,  # type: ignore[arg-type]
        )


def test_invalid_trade_setup_type():
    with pytest.raises(ValueError):
        StrategyResult(
            strategy_name="S",
            timestamp=1,
            proposed_action="buy",
            stability=_stability(),
            readiness=_readiness(),
            trade_setup={"entry": 1},  # type: ignore[arg-type]
        )


def test_immutability():
    result = StrategyResult(
        strategy_name="S",
        timestamp=1,
        proposed_action="hold",
        stability=_stability(),
        readiness=_readiness(),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.proposed_action = "buy"


def test_to_dict_includes_nested_models():
    result = StrategyResult(
        strategy_name="S",
        timestamp=1,
        proposed_action="buy",
        stability=_stability(),
        readiness=_readiness(),
        trade_setup=_buy_setup(),
    )
    payload = result.to_dict()
    assert payload["strategy_name"] == "S"
    assert payload["proposed_action"] == "buy"
    assert payload["stability"]["score"] == 0.8
    assert payload["readiness"]["approved"] is True
    assert payload["trade_setup"]["entry_price"] == 2000.0

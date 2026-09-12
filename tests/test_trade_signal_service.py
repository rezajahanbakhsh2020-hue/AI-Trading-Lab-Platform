import pytest

from src.platform.domain.readiness import Readiness
from src.platform.domain.stability import Stability
from src.platform.domain.strategy_result import StrategyResult
from src.platform.domain.trade_setup import TradeSetup
from src.platform.domain.trade_signal import TradeSignal
from src.platform.services import TradeSignalService


def _stability(risk_level="low", score=0.8):
    return Stability(score=score, risk_level=risk_level)


def _readiness(approved=True, reason=None, timestamp=1):
    return Readiness(approved=approved, reason=reason, timestamp=timestamp)


def _buy_setup(timestamp=10):
    return TradeSetup(
        symbol="XAUUSD",
        entry_price=2000.0,
        stop_loss=1990.0,
        take_profit_1=2020.0,
        take_profit_2=2030.0,
        take_profit_3=2040.0,
        timestamp=timestamp,
        direction="buy",
    )


def _sell_setup(timestamp=10):
    return TradeSetup(
        symbol="XAUUSD",
        entry_price=2000.0,
        stop_loss=2010.0,
        take_profit_1=1980.0,
        take_profit_2=1970.0,
        take_profit_3=1960.0,
        timestamp=timestamp,
        direction="sell",
    )


def _result(
    action="buy",
    approved=True,
    risk_level="low",
    setup=None,
    strategy_name="Momentum",
    timestamp=10,
    score=0.8,
    reason=None,
):
    if setup is None and action == "buy":
        setup = _buy_setup(timestamp)
    if setup is None and action == "sell":
        setup = _sell_setup(timestamp)
    return StrategyResult(
        strategy_name=strategy_name,
        timestamp=timestamp,
        proposed_action=action,
        stability=_stability(risk_level=risk_level, score=score),
        readiness=_readiness(approved=approved, reason=reason, timestamp=timestamp),
        trade_setup=setup,
    )


def test_buy_signal():
    service = TradeSignalService()
    result = service.generate(_result(action="buy"))
    assert isinstance(result, TradeSignal)
    assert result.tradable is True
    assert result.signal.action == "buy"
    assert result.signal.strategy_name == "Momentum"
    assert result.signal.timestamp == 10
    assert result.signal.confidence == 0.8
    assert result.trade_setup.entry_price == 2000.0
    assert result.reason == "trade signal approved"


def test_sell_signal():
    service = TradeSignalService()
    result = service.generate(_result(action="sell"))
    assert result.tradable is True
    assert result.signal.action == "sell"
    assert result.trade_setup.direction == "sell"


def test_no_signal_from_hold():
    service = TradeSignalService()
    result = service.generate(_result(action="hold", setup=_buy_setup()))
    assert result.tradable is False
    assert result.signal.action == "no-signal"
    assert result.trade_setup is None
    assert result.reason == "proposed action is hold"


def test_no_signal_from_no_signal_action():
    service = TradeSignalService()
    result = service.generate(_result(action="no-signal", setup=None))
    assert result.tradable is False
    assert result.signal.action == "no-signal"
    assert result.reason == "proposed action is no-signal"


def test_rejected_not_ready_strategy():
    service = TradeSignalService()
    result = service.generate(
        _result(approved=False, reason="drawdown exceeded")
    )
    assert result.tradable is False
    assert result.signal.action == "no-signal"
    assert result.signal.confidence is None
    assert result.reason == "drawdown exceeded"
    assert result.trade_setup is None


def test_not_ready_without_reason_uses_default():
    service = TradeSignalService()
    result = service.generate(_result(approved=False, reason=None))
    assert result.reason == "strategy is not trade-ready"


@pytest.mark.parametrize("risk_level", ["high", "critical"])
def test_unstable_strategy_is_not_tradable(risk_level):
    service = TradeSignalService()
    result = service.generate(_result(risk_level=risk_level, score=0.2))
    assert result.tradable is False
    assert result.signal.action == "no-signal"
    assert result.reason == "strategy stability risk is " + risk_level


@pytest.mark.parametrize("risk_level", ["low", "medium", "moderate", "minimal"])
def test_stable_risk_levels_allow_buy(risk_level):
    service = TradeSignalService()
    result = service.generate(_result(risk_level=risk_level, score=0.7))
    assert result.tradable is True
    assert result.signal.action == "buy"


def test_missing_trade_setup_is_no_signal():
    service = TradeSignalService()
    source = StrategyResult(
        strategy_name="Momentum",
        timestamp=10,
        proposed_action="buy",
        stability=_stability(),
        readiness=_readiness(approved=True),
        trade_setup=None,
    )
    result = service.generate(source)
    assert result.tradable is False
    assert result.reason == "trade setup is unavailable"


def test_mismatched_setup_direction_is_no_signal():
    service = TradeSignalService()
    result = service.generate(_result(action="buy", setup=_sell_setup()))
    assert result.tradable is False
    assert result.reason == "trade setup direction does not match proposed action"


def test_readiness_gate_precedes_stability():
    service = TradeSignalService()
    result = service.generate(
        _result(approved=False, reason="not ready", risk_level="critical")
    )
    assert result.reason == "not ready"


def test_deterministic_repeated_evaluation():
    service = TradeSignalService()
    source = _result(action="buy", timestamp=42, score=0.55)
    first = service.generate(source)
    second = service.generate(source)
    assert first == second
    assert first.to_dict() == second.to_dict()


def test_required_metadata_is_present():
    service = TradeSignalService()
    result = service.generate(_result(strategy_name="Breakout", timestamp=99))
    payload = result.to_dict()
    assert payload["signal"]["strategy_name"] == "Breakout"
    assert payload["signal"]["timestamp"] == 99
    assert payload["signal"]["action"] == "buy"
    assert payload["tradable"] is True
    assert payload["trade_setup"]["entry_price"] == 2000.0
    assert payload["stability"]["score"] == 0.8
    assert payload["readiness"]["approved"] is True


def test_invalid_input_type_raises():
    service = TradeSignalService()
    with pytest.raises(ValueError, match="StrategyResult"):
        service.generate(None)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        service.generate({"proposed_action": "buy"})  # type: ignore[arg-type]


def test_non_tradable_result_does_not_copy_setup():
    service = TradeSignalService()
    result = service.generate(_result(approved=False, reason="blocked"))
    assert result.trade_setup is None
    assert result.signal.strategy_name == "Momentum"
    assert result.signal.timestamp == 10

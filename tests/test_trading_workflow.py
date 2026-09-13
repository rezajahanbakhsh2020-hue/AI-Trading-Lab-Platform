"""Focused tests for Part 16 TradingWorkflowService and TradingWorkflowResult."""

import pytest

from src.platform.domain.autonomous_authorization import AutonomousAuthorization
from src.platform.domain.provider_readiness import PROVIDER_STATUS_NOT_READY, PROVIDER_STATUS_READY, ProviderReadiness
from src.platform.domain.provider_selection import SELECTION_STATUS_NOT_AVAILABLE, SELECTION_STATUS_SELECTED, ProviderSelection
from src.platform.domain.readiness import Readiness
from src.platform.domain.stability import Stability
from src.platform.domain.strategy_result import StrategyResult
from src.platform.domain.trade_readiness import TradeReadiness
from src.platform.domain.trade_setup import TradeSetup
from src.platform.domain.trade_signal import TradeSignal
from src.platform.domain.trading_workflow import (
    WORKFLOW_STATUS_DENIED,
    WORKFLOW_STATUS_EXECUTED,
    WORKFLOW_STATUS_NOT_READY,
    TradingWorkflowResult,
)
from src.platform.services.autonomous_authorization import AutonomousAuthorizationService
from src.platform.services.provider_selection import ProviderSelectionService
from src.platform.services.trade_signal import TradeSignalService
from src.platform.services.trading_workflow import (
    REASON_PROVIDER_NOT_READY,
    REASON_WORKFLOW_DENIED,
    REASON_WORKFLOW_EXECUTED,
    TradingWorkflowService,
)


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


def _strategy_result(action="buy", approved=True, risk_level="low", score=0.8, setup=None, timestamp=10.0):
    if setup is None and action == "buy":
        setup = _buy_setup(timestamp=timestamp)
    return StrategyResult(
        strategy_name="WorkflowStrategy",
        timestamp=timestamp,
        proposed_action=action,
        stability=Stability(score=score, risk_level=risk_level),
        readiness=Readiness(approved=approved, timestamp=timestamp),
        trade_setup=setup,
    )


def _selected_provider(provider_id="md1", category="market_data"):
    readiness = ProviderReadiness(
        provider_id=provider_id,
        category=category,
        status=PROVIDER_STATUS_READY,
        reason="ready",
    )
    return ProviderSelection(
        category=category,
        status=SELECTION_STATUS_SELECTED,
        reason="selected",
        selected_provider_id=provider_id,
        readiness=readiness,
        evaluated_readiness=(readiness,),
    )


def _unselected_provider(category="market_data"):
    readiness = ProviderReadiness(
        provider_id="md_bad",
        category=category,
        status=PROVIDER_STATUS_NOT_READY,
        reason="unhealthy",
    )
    return ProviderSelection(
        category=category,
        status=SELECTION_STATUS_NOT_AVAILABLE,
        reason="no ready provider",
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


class FakeSelectionService(ProviderSelectionService):
    def __init__(self, result: ProviderSelection):
        self._result = result

    def select_provider(self, *args, **kwargs):
        return self._result


def test_trading_workflow_executed_success():
    auth_svc = AutonomousAuthorizationService()
    sel_svc = FakeSelectionService(_selected_provider())
    workflow_svc = TradingWorkflowService(
        authorization_service=auth_svc,
        selection_service=sel_svc,
    )

    res = workflow_svc.run_workflow(
        symbol="XAUUSD",
        timeframe="1h",
        strategy_result=_strategy_result(action="buy"),
        timestamp=10.0,
        require_selected_provider=True,
    )

    assert isinstance(res, TradingWorkflowResult)
    assert res.status == WORKFLOW_STATUS_EXECUTED
    assert res.is_executed is True
    assert res.reason == REASON_WORKFLOW_EXECUTED
    assert res.authorization.is_authorized is True


def test_trading_workflow_denied_authorization():
    auth_svc = AutonomousAuthorizationService()
    workflow_svc = TradingWorkflowService(authorization_service=auth_svc)

    res = workflow_svc.run_workflow(
        symbol="XAUUSD",
        timeframe="1h",
        strategy_result=_strategy_result(action="hold"),
        timestamp=10.0,
    )

    assert res.status == WORKFLOW_STATUS_DENIED
    assert res.is_executed is False
    assert REASON_WORKFLOW_DENIED in res.reason
    assert res.authorization.is_authorized is False


def test_trading_workflow_not_ready_provider():
    auth_svc = AutonomousAuthorizationService()
    sel_svc = FakeSelectionService(_unselected_provider())
    workflow_svc = TradingWorkflowService(
        authorization_service=auth_svc,
        selection_service=sel_svc,
    )

    res = workflow_svc.run_workflow(
        symbol="XAUUSD",
        timeframe="1h",
        strategy_result=_strategy_result(action="buy"),
        require_selected_provider=True,
    )

    assert res.status == WORKFLOW_STATUS_NOT_READY
    assert res.is_executed is False
    assert REASON_PROVIDER_NOT_READY in res.reason


def test_trading_workflow_validation():
    auth_svc = AutonomousAuthorizationService()
    workflow_svc = TradingWorkflowService(authorization_service=auth_svc)

    with pytest.raises(ValueError):
        workflow_svc.run_workflow(symbol="", timeframe="1h")

    with pytest.raises(ValueError):
        workflow_svc.run_workflow(symbol="XAUUSD", timeframe="")


def test_trading_workflow_result_to_dict():
    auth_svc = AutonomousAuthorizationService()
    workflow_svc = TradingWorkflowService(authorization_service=auth_svc)

    res = workflow_svc.run_workflow(
        symbol="XAUUSD",
        timeframe="1h",
        strategy_result=_strategy_result(action="buy"),
        timestamp=10.0,
    )

    d = res.to_dict()
    assert d["symbol"] == "XAUUSD"
    assert d["timeframe"] == "1h"
    assert d["status"] == WORKFLOW_STATUS_EXECUTED
    assert d["is_executed"] is True
    assert "authorization" in d
    assert "trade_signal" in d

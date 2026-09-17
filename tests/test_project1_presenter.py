"""Unit tests for Project1SignalPresenter (Part 19 Presentation Service)."""

import pytest

from src.platform.adapters.project1_adapter import (
    DisconnectedProject1Adapter,
    Project1LabArtifactAdapter,
)
from src.platform.integrations.lab import LabArtifactSource
from src.platform.services.lab_artifacts import LabArtifactService
from src.platform.services.project1_presenter import Project1SignalPresenter


class DummyLabArtifactSource(LabArtifactSource):
    """Dummy LabArtifactSource for testing presenter integration."""

    def __init__(
        self,
        signal_data=None,
        setup_data=None,
        stability_data=None,
        source_name="DummyLabSource",
    ):
        self._signal = signal_data
        self._setup = setup_data
        self._stability = stability_data
        self._source_name = source_name
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def fetch_signal(self, symbol: str, timeframe: str):
        return self._signal

    def fetch_trade_setup(self, symbol: str, timeframe: str):
        return self._setup

    def fetch_stability(self, strategy_name: str):
        return self._stability

    def close(self) -> None:
        self.connected = False

    def describe(self):
        return {
            "name": self._source_name,
            "status": "active" if self.connected else "idle",
        }


def test_presenter_init_validation():
    with pytest.raises(ValueError, match="port must be a valid Project1IntegrationPort"):
        Project1SignalPresenter(None)  # type: ignore

    with pytest.raises(ValueError, match="port must be a valid Project1IntegrationPort"):
        Project1SignalPresenter("not_a_port")  # type: ignore


def test_presenter_with_disconnected_adapter():
    adapter = DisconnectedProject1Adapter()
    presenter = Project1SignalPresenter(adapter)

    res = presenter.present_signal("XAUUSD", "1h")
    assert res["connected"] is False
    assert res["status"] == "disconnected"
    assert res["signal"] is None
    assert "No Project 1 data connected yet" in res["message"]

    snapshot = presenter.build_host_snapshot("XAUUSD", "1h")
    assert snapshot["project1"]["connected"] is False
    assert snapshot["project1"]["status"] == "disconnected"
    assert snapshot["signal"]["action"] is None
    assert snapshot["risk"]["entry"] is None


def test_presenter_with_lab_adapter_full_signal_and_setup():
    source = DummyLabArtifactSource(
        signal_data={
            "action": "BUY",
            "strategy_name": "GoldTrendv1",
            "timestamp": 1700000000.0,
            "confidence": 0.88,
        },
        setup_data={
            "symbol": "XAUUSD",
            "entry_price": 2650.50,
            "stop_loss": 2635.00,
            "take_profit_1": 2670.00,
            "take_profit_2": 2690.00,
            "take_profit_3": 2710.00,
            "timestamp": 1700000000.0,
            "direction": "BUY",
        },
    )
    service = LabArtifactService(source)
    adapter = Project1LabArtifactAdapter(service)
    presenter = Project1SignalPresenter(adapter)

    res = presenter.present_signal("XAUUSD", "1h")
    assert res["connected"] is True
    assert res["status"] == "active"
    sig = res["signal"]
    assert sig["signal_type"] == "buy"
    assert sig["strategy_name"] == "GoldTrendv1"
    assert sig["confidence"] == 0.88
    assert sig["entry_price"] == 2650.50
    assert sig["stop_loss"] == 2635.00
    assert sig["take_profits"] == [2670.0, 2690.0, 2710.0]

    snapshot = presenter.build_host_snapshot("XAUUSD", "1h")
    assert snapshot["project1"]["connected"] is True
    assert snapshot["signal"]["action"] == "BUY"
    assert snapshot["signal"]["confidence"] == 0.88
    assert snapshot["risk"]["entry"] == 2650.50
    assert snapshot["risk"]["stopLoss"] == 2635.00
    assert snapshot["risk"]["takeProfits"] == [2670.0, 2690.0, 2710.0]
    assert snapshot["strategy"]["name"] == "GoldTrendv1"
    assert snapshot["strategy"]["stability"] == 88


def test_presenter_with_lab_adapter_no_signal():
    source = DummyLabArtifactSource(signal_data=None, setup_data=None)
    service = LabArtifactService(source)
    adapter = Project1LabArtifactAdapter(service)
    presenter = Project1SignalPresenter(adapter)

    res = presenter.present_signal("XAUUSD", "1h")
    assert res["connected"] is True
    assert res["status"] == "no-signal"
    assert res["signal"] is None

    snapshot = presenter.build_host_snapshot("XAUUSD", "1h")
    assert snapshot["project1"]["connected"] is True
    assert snapshot["signal"]["action"] == "NO SIGNAL"
    assert snapshot["risk"]["entry"] is None


def test_presenter_preserves_real_data_without_fabrication():
    source = DummyLabArtifactSource(
        signal_data={
            "action": "SELL",
            "strategy_name": "MeanReversion_Custom",
            "timestamp": 1712345678.0,
            "confidence": 0.72,
        },
        setup_data={
            "symbol": "EURUSD",
            "entry_price": 1.0850,
            "stop_loss": 1.0910,
            "take_profit_1": 1.0790,
            "take_profit_2": 1.0720,
            "take_profit_3": 1.0650,
            "timestamp": 1712345678.0,
            "direction": "SELL",
        },
    )
    service = LabArtifactService(source)
    adapter = Project1LabArtifactAdapter(service)
    presenter = Project1SignalPresenter(adapter)

    snapshot = presenter.build_host_snapshot("EURUSD", "4h")
    assert snapshot["market"]["symbol"] == "EURUSD"
    assert snapshot["signal"]["action"] == "SELL"
    assert snapshot["signal"]["confidence"] == 0.72
    assert snapshot["risk"]["entry"] == 1.0850
    assert snapshot["risk"]["stopLoss"] == 1.0910
    assert snapshot["risk"]["takeProfits"] == [1.0790, 1.0720, 1.0650]
    assert snapshot["strategy"]["name"] == "MeanReversion_Custom"


def test_presenter_order_intents_payload_and_isolation():
    from src.platform.domain.autonomous_authorization import AutonomousAuthorization
    from src.platform.domain.security import Permission
    from src.platform.domain.user_authorization import UserAuthorization
    from src.platform.services.order_intent import OrderIntentService

    adapter = DisconnectedProject1Adapter()
    order_intent_service = OrderIntentService()
    presenter = Project1SignalPresenter(adapter, order_intent_service=order_intent_service)

    user_a = UserAuthorization(
        user_id="user_a",
        auth_code="code_a",
        role="user",
        permissions=[Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS],
    )
    user_b = UserAuthorization(
        user_id="user_b",
        auth_code="code_b",
        role="user",
        permissions=[Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS],
    )

    # Initially empty state
    payload_a = presenter.get_order_intents_payload(user=user_a)
    assert payload_a == []

    # Create OrderIntent for user_a
    auth_a = AutonomousAuthorization(
        status="AUTHORIZED",
        reason="Approved",
        timestamp=1700000000.0,
        trade_signal=pytest.importorskip("src.platform.domain.trade_signal").TradeSignal(
            signal=pytest.importorskip("src.platform.domain.signal").Signal(
                action="buy", confidence=0.8, timestamp=1700000000.0, strategy_name="StratA"
            ),
            readiness=pytest.importorskip("src.platform.domain.readiness").Readiness(approved=True, reason="OK", timestamp=1700000000.0),
            stability=pytest.importorskip("src.platform.domain.stability").Stability(score=0.8, risk_level="low"),
            reason="Validated",
            tradable=True,
            trade_setup=pytest.importorskip("src.platform.domain.trade_setup").TradeSetup(
                symbol="XAUUSD",
                entry_price=2650.0,
                stop_loss=2630.0,
                take_profit_1=2680.0,
                take_profit_2=2700.0,
                take_profit_3=2720.0,
                timestamp=1700000000.0,
                direction="buy",
            ),
        ),
    )

    ok, msg, intent_a = order_intent_service.create_order_intent(
        user=user_a,
        authorization=auth_a,
        idempotency_key="key_a_123",
        requested_quantity=1.5,
    )
    assert ok is True
    assert intent_a is not None

    # Verify user_a sees their intent with exact level preservation and no price recalculations
    intents_a = presenter.get_order_intents_payload(user=user_a)
    assert len(intents_a) == 1
    item = intents_a[0]
    assert item["order_intent_id"] == intent_a.order_intent_id
    assert item["user_id"] == "user_a"
    assert item["symbol"] == "XAUUSD"
    assert item["direction"] == "buy"
    assert item["requested_price"] == 2650.0
    assert item["stop_loss"] == 2630.0
    assert item["take_profit_1"] == 2680.0
    assert item["lifecycle_state"] == "STAGED"
    assert item["is_staged"] is True
    assert item["is_terminal"] is False

    # Verify user_b (isolated user) receives empty payload
    intents_b = presenter.get_order_intents_payload(user=user_b)
    assert intents_b == []

    # Verify host snapshot carries user_a's orderIntents
    snapshot_a = presenter.build_host_snapshot(user=user_a)
    assert "orderIntents" in snapshot_a
    assert len(snapshot_a["orderIntents"]) == 1
    assert snapshot_a["orderIntents"][0]["order_intent_id"] == intent_a.order_intent_id

    # Verify host snapshot for user_b carries empty orderIntents
    snapshot_b = presenter.build_host_snapshot(user=user_b)
    assert snapshot_b["orderIntents"] == []

"""Tests for FileBackedOrderIntentRepository & OrderIntentService persistence integration."""

import os
import tempfile
import time
import pytest

from src.platform.adapters.order_intent_repository import FileBackedOrderIntentRepository
from src.platform.domain.autonomous_authorization import AutonomousAuthorization
from src.platform.domain.order_intent import OrderIntent, OrderLifecycleState
from src.platform.domain.readiness import Readiness
from src.platform.domain.signal import Signal
from src.platform.domain.stability import Stability
from src.platform.domain.trade_setup import TradeSetup
from src.platform.domain.trade_signal import TradeSignal
from src.platform.domain.user_authorization import UserAuthorization, UserRole
from src.platform.services.order_intent import OrderIntentService


def _create_sample_auth(user_id="customer1", symbol="XAUUSD", direction="buy"):
    sig = Signal(action=direction, confidence=0.85, timestamp=1700000000.0, strategy_name="TestStrat")
    readiness = Readiness(approved=True, reason="Ready", timestamp=1700000000.0)
    stability = Stability(score=0.85, risk_level="low")

    if direction == "sell":
        entry, sl, tp1, tp2, tp3 = 2000.0, 2020.0, 1980.0, 1960.0, 1940.0
    else:
        entry, sl, tp1, tp2, tp3 = 2000.0, 1980.0, 2030.0, 2050.0, 2080.0

    setup = TradeSetup(
        symbol=symbol,
        entry_price=entry,
        stop_loss=sl,
        take_profit_1=tp1,
        take_profit_2=tp2,
        take_profit_3=tp3,
        timestamp=1700000000.0,
        direction=direction,
    )
    trade_sig = TradeSignal(
        signal=sig,
        readiness=readiness,
        stability=stability,
        reason="Test signal",
        tradable=True,
        trade_setup=setup,
    )
    return AutonomousAuthorization(
        status="AUTHORIZED",
        reason="Approved for testing",
        trade_signal=trade_sig,
        timestamp=1700000000.0,
    )


def test_file_backed_order_intent_repository_lifecycle():
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "order_intents.json")
        repo = FileBackedOrderIntentRepository(storage_filepath=file_path)

        intent = OrderIntent(
            order_intent_id="ord_1",
            authorization_id="auth_1",
            user_id="cust1",
            symbol="XAUUSD",
            direction="buy",
            idempotency_key="idemp_1",
            creation_timestamp=1700000000.0,
            lifecycle_state=OrderLifecycleState.STAGED,
        )

        saved = repo.save_order_intent(intent)
        assert saved.order_intent_id == "ord_1"
        assert os.path.exists(file_path)

        # Reload from storage in new instance
        repo2 = FileBackedOrderIntentRepository(storage_filepath=file_path)
        retrieved = repo2.get_order_intent("ord_1", user_id="cust1")
        assert retrieved is not None
        assert retrieved.symbol == "XAUUSD"
        assert retrieved.lifecycle_state == OrderLifecycleState.STAGED

        # Idempotency lookup
        by_idemp = repo2.get_by_idempotency_key("cust1", "idemp_1")
        assert by_idemp is not None
        assert by_idemp.order_intent_id == "ord_1"


def test_order_intent_service_persistence():
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "order_intents.json")
        repo = FileBackedOrderIntentRepository(storage_filepath=file_path)
        svc = OrderIntentService(repository=repo)

        user = UserAuthorization(user_id="cust1", auth_code="code1", role=UserRole.CUSTOMER)
        auth = _create_sample_auth("cust1", "EURUSD", "sell")

        ok, msg, intent = svc.create_order_intent(
            user=user,
            authorization=auth,
            idempotency_key="key_100",
            symbol="EURUSD",
        )
        assert ok is True
        assert intent is not None
        assert intent.symbol == "EURUSD"

        # In new service instance using same repository file
        repo_reloaded = FileBackedOrderIntentRepository(storage_filepath=file_path)
        svc_reloaded = OrderIntentService(repository=repo_reloaded)

        ok_list, _, intents = svc_reloaded.list_order_intents(user=user)
        assert ok_list is True
        assert len(intents) == 1
        assert intents[0].order_intent_id == intent.order_intent_id

        # Update lifecycle state in reloaded service
        ok_up, msg_up, updated = svc_reloaded.transition_order_intent_state(
            user=user,
            order_intent_id=intent.order_intent_id,
            target_state=OrderLifecycleState.CANCELLED,
            reason="User cancelled order",
        )
        assert ok_up is True
        assert updated.lifecycle_state == OrderLifecycleState.CANCELLED

        # Verify state persisted on disk
        repo_verify = FileBackedOrderIntentRepository(storage_filepath=file_path)
        persisted = repo_verify.get_order_intent(intent.order_intent_id, user_id="cust1")
        assert persisted.lifecycle_state == OrderLifecycleState.CANCELLED

"""Comprehensive tests for Order Intent Domain Contract, Lifecycle Model, and Application Service.

Verifies:
- Valid authorized OrderIntent creation
- Unauthorized creation rejection
- Malformed/invalid input handling
- Missing required upstream data handling
- User and tenant isolation
- Idempotency support
- Deterministic lifecycle transitions
- Terminal state protection against invalid transitions
- Platform Audit Control integration
- Honest status semantics without false execution claims
- Preservation of upstream Entry/SL/TP data without recalculation
"""

import time
import pytest

from src.platform.domain.audit_control import AuditCategory, OperationalLifecycleState
from src.platform.domain.autonomous_authorization import (
    AUTHORIZATION_STATUS_AUTHORIZED,
    AUTHORIZATION_STATUS_REJECTED,
    AutonomousAuthorization,
)
from src.platform.domain.order_intent import (
    OrderIntent,
    OrderLifecycleState,
    validate_lifecycle_transition,
)
from src.platform.domain.provider_selection import ProviderSelection
from src.platform.domain.readiness import Readiness
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.signal import Signal
from src.platform.domain.stability import Stability
from src.platform.domain.trade_readiness import TradeReadiness
from src.platform.domain.trade_setup import TradeSetup
from src.platform.domain.trade_signal import TradeSignal
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.order_intent import OrderIntentService


@pytest.fixture
def normal_user_a():
    return UserAuthorization(
        user_id="user_a",
        auth_code="auth_code_a",
        role=UserRole.USER,
        permissions=(Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS),
    )


@pytest.fixture
def normal_user_b():
    return UserAuthorization(
        user_id="user_b",
        auth_code="auth_code_b",
        role=UserRole.USER,
        permissions=(Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS),
    )


@pytest.fixture
def admin_user():
    return UserAuthorization(
        user_id="admin_user",
        auth_code="auth_code_admin",
        role=UserRole.ADMIN,
        permissions=(Permission.ADMIN_ALL,),
    )


@pytest.fixture
def sample_trade_setup():
    return TradeSetup(
        symbol="XAUUSD",
        entry_price=2650.50,
        stop_loss=2635.00,
        take_profit_1=2670.00,
        take_profit_2=2690.00,
        take_profit_3=2710.00,
        timestamp=1700000000.0,
        direction="buy",
    )


@pytest.fixture
def sample_trade_signal(sample_trade_setup):
    signal = Signal(
        action="buy",
        strategy_name="GoldTrendv1",
        timestamp=1700000000.0,
        confidence=0.85,
    )
    readiness = Readiness(approved=True, reason="All systems operational", timestamp=1700000000.0)
    stability = Stability(score=0.90, risk_level="low")
    return TradeSignal(
        signal=signal,
        readiness=readiness,
        stability=stability,
        reason="Tradable buy signal emitted",
        tradable=True,
        trade_setup=sample_trade_setup,
    )


@pytest.fixture
def authorized_autonomous_result(sample_trade_signal):
    provider_sel = ProviderSelection(
        category="market_data",
        status="SELECTED",
        selected_provider_id="biquote_provider",
        reason="Primary provider selected",
    )
    trade_readiness = TradeReadiness(
        symbol="XAUUSD",
        timeframe="1h",
        direction="buy",
        entry_price=2650.50,
        stop_loss=2635.00,
        take_profit_1=2670.00,
        take_profit_2=2690.00,
        take_profit_3=2710.00,
        risk_reward_to_tp1=1.3,
        levels_are_sane=True,
    )
    return AutonomousAuthorization(
        status=AUTHORIZATION_STATUS_AUTHORIZED,
        reason="autonomous execution authorized",
        timestamp=1700000000.0,
        trade_signal=sample_trade_signal,
        provider_selection=provider_sel,
        trade_readiness=trade_readiness,
    )


@pytest.fixture
def rejected_autonomous_result(sample_trade_signal):
    return AutonomousAuthorization(
        status=AUTHORIZATION_STATUS_REJECTED,
        reason="trade signal is not tradable",
        timestamp=1700000000.0,
        trade_signal=sample_trade_signal,
    )


@pytest.fixture
def audit_control():
    return PlatformAuditControlService()


@pytest.fixture
def order_intent_service(audit_control):
    return OrderIntentService(audit_control=audit_control)


def test_valid_authorized_order_intent_creation(
    normal_user_a, authorized_autonomous_result, order_intent_service, sample_trade_setup
):
    """Verify creating an OrderIntent from a valid authorized result preserves upstream values verbatim."""
    success, msg, intent = order_intent_service.create_order_intent(
        user=normal_user_a,
        authorization=authorized_autonomous_result,
        idempotency_key="idemp_001",
        order_type="market",
        requested_quantity=1.5,
        time_in_force="GTC",
        timestamp=1700000100.0,
    )

    assert success is True
    assert "staged successfully" in msg
    assert intent is not None
    assert intent.user_id == "user_a"
    assert intent.symbol == "XAUUSD"
    assert intent.direction == "buy"
    assert intent.lifecycle_state == OrderLifecycleState.STAGED
    assert intent.is_staged is True
    assert intent.is_terminal is False

    # Upstream data preserved verbatim without recalculation
    assert intent.requested_price == sample_trade_setup.entry_price
    assert intent.stop_loss == sample_trade_setup.stop_loss
    assert intent.take_profit_1 == sample_trade_setup.take_profit_1
    assert intent.take_profit_2 == sample_trade_setup.take_profit_2
    assert intent.take_profit_3 == sample_trade_setup.take_profit_3
    assert intent.requested_quantity == 1.5
    assert intent.time_in_force == "GTC"


def test_unauthorized_autonomous_authorization_rejection(
    normal_user_a, rejected_autonomous_result, order_intent_service
):
    """Verify that a REJECTED AutonomousAuthorization cannot produce an OrderIntent."""
    success, msg, intent = order_intent_service.create_order_intent(
        user=normal_user_a,
        authorization=rejected_autonomous_result,
        idempotency_key="idemp_002",
    )

    assert success is False
    assert "not authorized" in msg
    assert intent is None


def test_unauthorized_user_rejection(authorized_autonomous_result, order_intent_service):
    """Verify unauthenticated/unauthorized user cannot create an order intent."""
    success, msg, intent = order_intent_service.create_order_intent(
        user=None,
        authorization=authorized_autonomous_result,
        idempotency_key="idemp_003",
    )

    assert success is False
    assert "Unauthorized" in msg
    assert intent is None


def test_malformed_and_missing_data_handling(
    normal_user_a, authorized_autonomous_result, order_intent_service
):
    """Verify rejection when idempotency key or required upstream data is missing/invalid."""
    # Empty idempotency key
    success, msg, intent = order_intent_service.create_order_intent(
        user=normal_user_a,
        authorization=authorized_autonomous_result,
        idempotency_key="",
    )
    assert success is False
    assert "idempotency_key" in msg

    # Trade signal with no trade setup and no symbol provided
    signal_no_setup = Signal(
        action="buy", strategy_name="Strat1", timestamp=1700000000.0
    )
    trade_sig_no_setup = TradeSignal(
        signal=signal_no_setup,
        readiness=Readiness(approved=True, reason="Ready", timestamp=1700000000.0),
        stability=Stability(score=1.0, risk_level="low"),
        reason="Tradable",
        tradable=True,
        trade_setup=None,
    )
    auth_no_setup = AutonomousAuthorization(
        status=AUTHORIZATION_STATUS_AUTHORIZED,
        reason="authorized",
        timestamp=1700000000.0,
        trade_signal=trade_sig_no_setup,
    )

    success, msg, intent = order_intent_service.create_order_intent(
        user=normal_user_a,
        authorization=auth_no_setup,
        idempotency_key="idemp_004",
        symbol=None,
    )
    assert success is False
    assert "Missing required symbol" in msg


def test_user_tenant_isolation(
    normal_user_a, normal_user_b, admin_user, authorized_autonomous_result, order_intent_service
):
    """Verify strict multi-tenant isolation between users."""
    # User A creates order intent
    success, _, intent_a = order_intent_service.create_order_intent(
        user=normal_user_a,
        authorization=authorized_autonomous_result,
        idempotency_key="user_a_key_1",
    )
    assert success is True

    # User B attempts to retrieve User A's order intent
    get_success, get_msg, retrieved = order_intent_service.get_order_intent(
        user=normal_user_b,
        order_intent_id=intent_a.order_intent_id,
    )
    assert get_success is False
    assert "Unauthorized" in get_msg
    assert retrieved is None

    # User B attempts to transition User A's order intent
    trans_success, trans_msg, _ = order_intent_service.transition_order_intent_state(
        user=normal_user_b,
        order_intent_id=intent_a.order_intent_id,
        target_state=OrderLifecycleState.CANCELLED,
    )
    assert trans_success is False
    assert "Unauthorized" in trans_msg

    # Admin user can access User A's order intent
    admin_get_success, _, admin_retrieved = order_intent_service.get_order_intent(
        user=admin_user,
        order_intent_id=intent_a.order_intent_id,
    )
    assert admin_get_success is True
    assert admin_retrieved.order_intent_id == intent_a.order_intent_id

    # User B's listing contains only User B's intents
    list_success, _, list_b = order_intent_service.list_order_intents(user=normal_user_b)
    assert list_success is True
    assert len(list_b) == 0


def test_idempotency_support(
    normal_user_a, authorized_autonomous_result, order_intent_service
):
    """Verify that reusing the same idempotency key returns the existing OrderIntent without duplication."""
    success_1, _, intent_1 = order_intent_service.create_order_intent(
        user=normal_user_a,
        authorization=authorized_autonomous_result,
        idempotency_key="idemp_reuse_key",
    )
    assert success_1 is True

    success_2, msg_2, intent_2 = order_intent_service.create_order_intent(
        user=normal_user_a,
        authorization=authorized_autonomous_result,
        idempotency_key="idemp_reuse_key",
    )
    assert success_2 is True
    assert "idempotent" in msg_2
    assert intent_1.order_intent_id == intent_2.order_intent_id


def test_deterministic_lifecycle_transitions(
    normal_user_a, authorized_autonomous_result, order_intent_service
):
    """Verify legal state transitions: STAGED -> CANCELLED / EXPIRED / REJECTED."""
    # Test STAGED -> CANCELLED
    _, _, intent = order_intent_service.create_order_intent(
        user=normal_user_a,
        authorization=authorized_autonomous_result,
        idempotency_key="idemp_trans_1",
    )
    success, msg, updated = order_intent_service.transition_order_intent_state(
        user=normal_user_a,
        order_intent_id=intent.order_intent_id,
        target_state=OrderLifecycleState.CANCELLED,
        reason="User requested cancellation",
    )
    assert success is True
    assert updated.lifecycle_state == OrderLifecycleState.CANCELLED
    assert updated.is_terminal is True
    assert updated.rejection_reason == "User requested cancellation"

    # Test STAGED -> EXPIRED
    _, _, intent_exp = order_intent_service.create_order_intent(
        user=normal_user_a,
        authorization=authorized_autonomous_result,
        idempotency_key="idemp_trans_2",
    )
    success, _, updated_exp = order_intent_service.transition_order_intent_state(
        user=normal_user_a,
        order_intent_id=intent_exp.order_intent_id,
        target_state=OrderLifecycleState.EXPIRED,
        reason="Time window expired",
    )
    assert success is True
    assert updated_exp.lifecycle_state == OrderLifecycleState.EXPIRED
    assert updated_exp.is_terminal is True


def test_invalid_lifecycle_transitions_and_terminal_protection(
    normal_user_a, authorized_autonomous_result, order_intent_service
):
    """Verify that terminal states (CANCELLED, EXPIRED, REJECTED) cannot transition to any state."""
    _, _, intent = order_intent_service.create_order_intent(
        user=normal_user_a,
        authorization=authorized_autonomous_result,
        idempotency_key="idemp_term_1",
    )

    # Move to CANCELLED
    order_intent_service.transition_order_intent_state(
        user=normal_user_a,
        order_intent_id=intent.order_intent_id,
        target_state=OrderLifecycleState.CANCELLED,
    )

    # Attempt illegal transition: CANCELLED -> STAGED
    success, msg, current = order_intent_service.transition_order_intent_state(
        user=normal_user_a,
        order_intent_id=intent.order_intent_id,
        target_state=OrderLifecycleState.STAGED,
    )
    assert success is False
    assert "terminal state" in msg.lower()
    assert current.lifecycle_state == OrderLifecycleState.CANCELLED

    # Direct domain validation call test
    with pytest.raises(ValueError, match="terminal state"):
        validate_lifecycle_transition(OrderLifecycleState.CANCELLED, OrderLifecycleState.EXPIRED)


def test_audit_integration(
    normal_user_a, admin_user, authorized_autonomous_result, order_intent_service, audit_control
):
    """Verify that order intent operations record accurate audit events without claiming broker execution."""
    order_intent_service.create_order_intent(
        user=normal_user_a,
        authorization=authorized_autonomous_result,
        idempotency_key="idemp_audit_1",
    )

    success, msg, events = audit_control.query_events(
        user=admin_user,
        filter_params=None,
    )
    assert success is True

    intent_events = [e for e in events if e.category == AuditCategory.ORDER_INTENT]
    assert len(intent_events) > 0

    staged_event = next(e for e in intent_events if e.event_type == "ORDER_INTENT_STAGED")
    assert staged_event.user_id == "user_a"
    assert staged_event.lifecycle_state == OperationalLifecycleState.STAGED
    assert "without external execution" in staged_event.details


def test_no_false_execution_claims():
    """Verify lifecycle states forbid ROUTED, ACCEPTED, FILLED, or EXECUTED states."""
    valid_states = [s.value for s in OrderLifecycleState]
    assert "STAGED" in valid_states
    assert "REJECTED" in valid_states
    assert "CANCELLED" in valid_states
    assert "EXPIRED" in valid_states

    for forbidden in ("ROUTED", "ACCEPTED", "FILLED", "EXECUTED", "PLACED"):
        assert forbidden not in valid_states

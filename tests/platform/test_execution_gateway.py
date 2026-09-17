"""Unit tests for Execution Gateway Boundary (Part 17).

Tests domain models, adapter fail-closed behavior, ExecutionGatewayService security,
user isolation, OrderIntent lifecycle checks, command derivation, and audit logging.
"""

import pytest

from src.platform.adapters.execution_gateway import UnavailableExecutionAdapter
from src.platform.domain.audit_control import AuditCategory, OperationalLifecycleState
from src.platform.domain.autonomous_authorization import (
    AUTHORIZATION_STATUS_AUTHORIZED,
    AutonomousAuthorization,
)
from src.platform.domain.execution_gateway import (
    ExecutionAttemptResult,
    ExecutionBoundaryStatus,
    ExecutionRequestCommand,
)
from src.platform.domain.order_intent import OrderIntent, OrderLifecycleState
from src.platform.domain.readiness import Readiness
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.signal import Signal
from src.platform.domain.stability import Stability
from src.platform.domain.trade_setup import TradeSetup
from src.platform.domain.trade_signal import TradeSignal
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.execution_gateway import ExecutionGatewayService
from src.platform.services.order_intent import OrderIntentService
from src.platform.services.security import SecurityBoundaryService


def _create_sample_staged_intent(
    user_id: str = "user_100",
    order_intent_id: str = "ord_100",
    symbol: str = "XAUUSD",
    direction: str = "buy",
    lifecycle_state: OrderLifecycleState = OrderLifecycleState.STAGED,
) -> OrderIntent:
    return OrderIntent(
        order_intent_id=order_intent_id,
        authorization_id="auth_100",
        user_id=user_id,
        symbol=symbol,
        direction=direction,
        idempotency_key="idemp_100",
        creation_timestamp=1700000000.0,
        lifecycle_state=lifecycle_state,
        order_type="market",
        requested_price=2650.0,
        requested_quantity=1.0,
        stop_loss=2635.0,
        take_profit_1=2670.0,
    )


def test_execution_request_command_from_order_intent():
    intent = _create_sample_staged_intent()
    cmd = ExecutionRequestCommand.from_order_intent(intent, command_id="cmd_999", timestamp=1700000100.0)

    assert cmd.execution_command_id == "cmd_999"
    assert cmd.order_intent_id == intent.order_intent_id
    assert cmd.user_id == intent.user_id
    assert cmd.symbol == "XAUUSD"
    assert cmd.direction == "buy"
    assert cmd.requested_price == 2650.0
    assert cmd.stop_loss == 2635.0
    assert cmd.take_profit_1 == 2670.0
    assert cmd.timestamp == 1700000100.0


def test_execution_request_command_rejects_non_staged_intent():
    intent = _create_sample_staged_intent(lifecycle_state=OrderLifecycleState.CANCELLED)

    with pytest.raises(ValueError, match="non-staged state"):
        ExecutionRequestCommand.from_order_intent(intent)


def test_unavailable_execution_adapter():
    adapter = UnavailableExecutionAdapter(provider_id="test_adapter")
    intent = _create_sample_staged_intent()
    cmd = ExecutionRequestCommand.from_order_intent(intent)

    result = adapter.request_execution(cmd)

    assert isinstance(result, ExecutionAttemptResult)
    assert result.success is False
    assert result.externally_executed is False
    assert result.status == ExecutionBoundaryStatus.UNCONFIGURED
    assert result.user_id == "user_100"
    assert result.order_intent_id == "ord_100"

    desc = adapter.describe()
    assert desc["configured"] is False
    assert desc["allows_execution"] is False


def test_execution_gateway_service_unauthenticated():
    service = ExecutionGatewayService()
    res = service.request_execution(user=None, order_intent_id="ord_100")

    assert res.success is False
    assert res.status == ExecutionBoundaryStatus.REJECTED_UNAUTHORIZED
    assert res.externally_executed is False


def test_execution_gateway_service_success_workflow():
    sec_boundary = SecurityBoundaryService()
    audit_control = PlatformAuditControlService(security_boundary=sec_boundary)
    order_service = OrderIntentService(security_boundary=sec_boundary, audit_control=audit_control)

    user = UserAuthorization(
        user_id="user_1",
        auth_code="code_1",
        role=UserRole.USER,
        permissions=(Permission.READ_SIGNALS,),
    )

    sig = Signal(action="buy", confidence=0.85, timestamp=1700000000.0, strategy_name="Strat1")
    setup = TradeSetup(
        symbol="XAUUSD",
        entry_price=2650.0,
        stop_loss=2635.0,
        take_profit_1=2670.0,
        take_profit_2=2690.0,
        take_profit_3=2710.0,
        timestamp=1700000000.0,
        direction="buy",
    )
    readiness = Readiness(approved=True, reason="Approved", timestamp=1700000000.0)
    stability = Stability(score=0.85, risk_level="low")
    trade_sig = TradeSignal(
        signal=sig,
        tradable=True,
        trade_setup=setup,
        readiness=readiness,
        stability=stability,
        reason="Test trade signal",
    )
    auth = AutonomousAuthorization(
        status=AUTHORIZATION_STATUS_AUTHORIZED,
        reason="Authorized",
        timestamp=1700000000.0,
        trade_signal=trade_sig,
    )

    success, msg, intent = order_service.create_order_intent(
        user=user,
        authorization=auth,
        idempotency_key="idemp_flow_1",
        symbol="XAUUSD",
    )
    assert success is True
    assert intent is not None

    service = ExecutionGatewayService(
        order_intent_service=order_service,
        security_boundary=sec_boundary,
        audit_control=audit_control,
    )

    res = service.request_execution(user=user, order_intent_id=intent.order_intent_id)

    assert res.success is False
    assert res.externally_executed is False
    assert res.status == ExecutionBoundaryStatus.UNCONFIGURED
    assert res.user_id == "user_1"
    assert res.order_intent_id == intent.order_intent_id

    # Verify audit event recorded
    _, _, events = audit_control.query_events(user=user)
    exec_events = [e for e in events if e.event_type.startswith("EXECUTION_BOUNDARY_")]
    assert len(exec_events) >= 1
    assert exec_events[0].resource_id == intent.order_intent_id


def test_execution_gateway_service_tenant_isolation():
    sec_boundary = SecurityBoundaryService()
    audit_control = PlatformAuditControlService(security_boundary=sec_boundary)
    order_service = OrderIntentService(security_boundary=sec_boundary, audit_control=audit_control)

    user1 = UserAuthorization(user_id="user_1", auth_code="code_1", role=UserRole.USER, permissions=(Permission.READ_SIGNALS,))
    user2 = UserAuthorization(user_id="user_2", auth_code="code_2", role=UserRole.USER, permissions=(Permission.READ_SIGNALS,))

    sig = Signal(action="buy", confidence=0.85, timestamp=1700000000.0, strategy_name="Strat1")
    setup = TradeSetup(
        symbol="XAUUSD",
        entry_price=2650.0,
        stop_loss=2635.0,
        take_profit_1=2670.0,
        take_profit_2=2690.0,
        take_profit_3=2710.0,
        timestamp=1700000000.0,
        direction="buy",
    )
    readiness = Readiness(approved=True, reason="Approved", timestamp=1700000000.0)
    stability = Stability(score=0.85, risk_level="low")
    trade_sig = TradeSignal(
        signal=sig,
        tradable=True,
        trade_setup=setup,
        readiness=readiness,
        stability=stability,
        reason="Test trade signal",
    )
    auth = AutonomousAuthorization(
        status=AUTHORIZATION_STATUS_AUTHORIZED,
        reason="Authorized",
        timestamp=1700000000.0,
        trade_signal=trade_sig,
    )

    success, _, intent = order_service.create_order_intent(
        user=user1,
        authorization=auth,
        idempotency_key="idemp_u1",
        symbol="XAUUSD",
    )
    assert success is True

    service = ExecutionGatewayService(
        order_intent_service=order_service,
        security_boundary=sec_boundary,
        audit_control=audit_control,
    )

    # User 2 attempts to request execution for User 1's intent
    res = service.request_execution(user=user2, order_intent_id=intent.order_intent_id)

    assert res.success is False
    assert res.status == ExecutionBoundaryStatus.REJECTED_INVALID_STATE
    assert "not accessible" in res.reason.lower()


def test_execution_gateway_service_rejects_cancelled_intent():
    sec_boundary = SecurityBoundaryService()
    audit_control = PlatformAuditControlService(security_boundary=sec_boundary)
    order_service = OrderIntentService(security_boundary=sec_boundary, audit_control=audit_control)

    user = UserAuthorization(user_id="user_1", auth_code="code_1", role=UserRole.USER, permissions=(Permission.READ_SIGNALS,))

    sig = Signal(action="buy", confidence=0.85, timestamp=1700000000.0, strategy_name="Strat1")
    setup = TradeSetup(
        symbol="XAUUSD",
        entry_price=2650.0,
        stop_loss=2635.0,
        take_profit_1=2670.0,
        take_profit_2=2690.0,
        take_profit_3=2710.0,
        timestamp=1700000000.0,
        direction="buy",
    )
    readiness = Readiness(approved=True, reason="Approved", timestamp=1700000000.0)
    stability = Stability(score=0.85, risk_level="low")
    trade_sig = TradeSignal(
        signal=sig,
        tradable=True,
        trade_setup=setup,
        readiness=readiness,
        stability=stability,
        reason="Test trade signal",
    )
    auth = AutonomousAuthorization(
        status=AUTHORIZATION_STATUS_AUTHORIZED,
        reason="Authorized",
        timestamp=1700000000.0,
        trade_signal=trade_sig,
    )

    _, _, intent = order_service.create_order_intent(
        user=user,
        authorization=auth,
        idempotency_key="idemp_cancel_test",
        symbol="XAUUSD",
    )

    # Cancel intent first
    order_service.transition_order_intent_state(
        user=user,
        order_intent_id=intent.order_intent_id,
        target_state=OrderLifecycleState.CANCELLED,
        reason="User cancelled",
    )

    service = ExecutionGatewayService(
        order_intent_service=order_service,
        security_boundary=sec_boundary,
        audit_control=audit_control,
    )

    res = service.request_execution(user=user, order_intent_id=intent.order_intent_id)

    assert res.success is False
    assert res.status == ExecutionBoundaryStatus.REJECTED_INVALID_STATE
    assert "non-staged lifecycle state 'CANCELLED'" in res.reason


def test_execution_gateway_idempotency_and_attempts_history():
    sec_boundary = SecurityBoundaryService()
    audit_control = PlatformAuditControlService(security_boundary=sec_boundary)
    order_service = OrderIntentService(security_boundary=sec_boundary, audit_control=audit_control)

    user = UserAuthorization(user_id="user_1", auth_code="code_1", role=UserRole.USER, permissions=(Permission.READ_SIGNALS,))

    sig = Signal(action="buy", confidence=0.85, timestamp=1700000000.0, strategy_name="Strat1")
    setup = TradeSetup(
        symbol="XAUUSD", entry_price=2650.0, stop_loss=2635.0, take_profit_1=2670.0, take_profit_2=2690.0, take_profit_3=2710.0, timestamp=1700000000.0, direction="buy"
    )
    trade_sig = TradeSignal(signal=sig, tradable=True, trade_setup=setup, readiness=Readiness(approved=True, reason="OK", timestamp=1700000000.0), stability=Stability(score=0.85, risk_level="low"), reason="OK")
    auth = AutonomousAuthorization(status=AUTHORIZATION_STATUS_AUTHORIZED, reason="OK", timestamp=1700000000.0, trade_signal=trade_sig)

    _, _, intent = order_service.create_order_intent(
        user=user, authorization=auth, idempotency_key="idemp_history_test", symbol="XAUUSD"
    )

    service = ExecutionGatewayService(
        order_intent_service=order_service, security_boundary=sec_boundary, audit_control=audit_control
    )

    res1 = service.request_execution(user=user, order_intent_id=intent.order_intent_id)
    res2 = service.request_execution(user=user, order_intent_id=intent.order_intent_id)

    # Idempotent call returns identical result
    assert res1 == res2
    assert res1.is_rejected is True
    assert res1.is_accepted is False
    assert res1.is_failed is False

    # Check attempt retrieval
    ok, msg, attempts = service.get_execution_attempts(user=user, order_intent_id=intent.order_intent_id)
    assert ok is True
    assert len(attempts) == 1
    assert attempts[0]["order_intent_id"] == intent.order_intent_id


def test_execution_gateway_service_adapter_exception_fail_closed():
    sec_boundary = SecurityBoundaryService()
    audit_control = PlatformAuditControlService(security_boundary=sec_boundary)
    order_service = OrderIntentService(security_boundary=sec_boundary, audit_control=audit_control)

    user = UserAuthorization(user_id="user_1", auth_code="code_1", role=UserRole.USER, permissions=(Permission.READ_SIGNALS,))

    sig = Signal(action="buy", confidence=0.85, timestamp=1700000000.0, strategy_name="Strat1")
    setup = TradeSetup(
        symbol="XAUUSD", entry_price=2650.0, stop_loss=2635.0, take_profit_1=2670.0, take_profit_2=2690.0, take_profit_3=2710.0, timestamp=1700000000.0, direction="buy"
    )
    trade_sig = TradeSignal(signal=sig, tradable=True, trade_setup=setup, readiness=Readiness(approved=True, reason="OK", timestamp=1700000000.0), stability=Stability(score=0.85, risk_level="low"), reason="OK")
    auth = AutonomousAuthorization(status=AUTHORIZATION_STATUS_AUTHORIZED, reason="OK", timestamp=1700000000.0, trade_signal=trade_sig)

    _, _, intent = order_service.create_order_intent(
        user=user, authorization=auth, idempotency_key="idemp_fail_closed", symbol="XAUUSD"
    )

    class BrokenAdapter:
        def request_execution(self, command):
            raise RuntimeError("Fatal adapter failure with secret_token=12345")
        def describe(self):
            return {}

    service = ExecutionGatewayService(
        order_intent_service=order_service,
        execution_port=BrokenAdapter(),
        security_boundary=sec_boundary,
        audit_control=audit_control,
    )

    res = service.request_execution(user=user, order_intent_id=intent.order_intent_id)

    assert res.success is False
    assert res.status == ExecutionBoundaryStatus.FAILED_AT_BOUNDARY
    assert res.is_failed is True
    assert res.externally_executed is False
    assert "secret_token" not in res.detail
    assert "[REDACTED]" in res.detail

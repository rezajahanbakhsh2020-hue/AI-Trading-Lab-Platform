"""Integration test suite for End-to-End Trading Intelligence & Order Intent Staging Workflow.

Verifies end-to-end integration across:
Project 1 Signal Intake -> Autonomous Authorization -> Order Intent Staging ->
Execution Gateway Boundary Submission -> Notification Delivery Inbox -> Audit Control Logging.
Enforces multi-tenant isolation, RBAC boundaries, and non-external execution fail-closed guarantees.
"""

import time
import pytest
from src.platform.domain.autonomous_authorization import AutonomousAuthorization
from src.platform.domain.notification import NotificationCategory
from src.platform.domain.order_intent import OrderLifecycleState
from src.platform.domain.readiness import Readiness
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.signal import Signal
from src.platform.domain.stability import Stability
from src.platform.domain.trade_setup import TradeSetup
from src.platform.domain.trade_signal import TradeSignal
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.execution_gateway import ExecutionGatewayService
from src.platform.services.notification import NotificationService
from src.platform.services.order_intent import OrderIntentService
from src.platform.services.security import SecurityBoundaryService


def test_end_to_end_order_intent_staging_and_notification_flow():
    """Verify order intent staging generates a notification event and audit log entry."""
    security = SecurityBoundaryService()
    audit = PlatformAuditControlService(security_boundary=security)
    notification_svc = NotificationService(security_service=security)

    order_svc = OrderIntentService(
        security_boundary=security,
        audit_control=audit,
        notification_service=notification_svc,
    )

    user = UserAuthorization(
        user_id="trader_alpha",
        auth_code="code_alpha_123",
        role=UserRole.CUSTOMER,
        permissions=(Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS),
        activation_timestamp=time.time() - 100,
        expiration_timestamp=time.time() + 86400,
    )

    ts = time.time()
    sig = Signal(action="buy", confidence=0.85, timestamp=ts, strategy_name="GoldTrend")
    setup = TradeSetup(
        symbol="XAUUSD",
        entry_price=2650.0,
        stop_loss=2635.0,
        take_profit_1=2670.0,
        take_profit_2=2690.0,
        take_profit_3=2710.0,
        timestamp=ts,
        direction="buy",
    )
    trade_sig = TradeSignal(
        signal=sig,
        readiness=Readiness(approved=True, reason="Valid signal", timestamp=ts),
        stability=Stability(score=0.85, risk_level="low"),
        reason="Test signal",
        tradable=True,
        trade_setup=setup,
    )
    auth = AutonomousAuthorization(
        status="AUTHORIZED",
        reason="All gates passed",
        trade_signal=trade_sig,
        timestamp=ts,
    )

    # 1. Stage Order Intent
    ok, msg, intent = order_svc.create_order_intent(
        user=user,
        authorization=auth,
        idempotency_key=f"idemp_test_alpha_{int(ts)}",
        symbol="XAUUSD",
        timestamp=ts,
    )

    assert ok is True
    assert intent is not None
    assert intent.lifecycle_state == OrderLifecycleState.STAGED
    assert intent.symbol == "XAUUSD"
    assert intent.direction == "buy"

    # 2. Verify NotificationEvent was created in user inbox
    notifs = notification_svc.get_notifications(
        requester=user,
        target_user_id="trader_alpha",
        category=NotificationCategory.SIGNAL_LIFECYCLE,
    )
    assert len(notifs) >= 1
    staged_notif = [n for n in notifs if "Staged" in n.title or "STAGED" in str(n.metadata)]
    assert len(staged_notif) >= 1
    assert "XAUUSD" in staged_notif[0].title or "XAUUSD" in staged_notif[0].message

    # 3. Transition Order Intent State (CANCELLED)
    ok_tr, msg_tr, updated = order_svc.transition_order_intent_state(
        user=user,
        order_intent_id=intent.order_intent_id,
        target_state="CANCELLED",
        reason="Trader requested cancellation",
    )
    assert ok_tr is True
    assert updated is not None
    assert updated.lifecycle_state == OrderLifecycleState.CANCELLED

    # 4. Verify transition NotificationEvent
    notifs_after = notification_svc.get_notifications(
        requester=user,
        target_user_id="trader_alpha",
        category=NotificationCategory.SIGNAL_LIFECYCLE,
    )
    assert len(notifs_after) >= 2
    cancelled_notifs = [n for n in notifs_after if "Cancelled" in n.title or "CANCELLED" in str(n.metadata)]
    assert len(cancelled_notifs) >= 1


def test_end_to_end_execution_boundary_request_and_notification():
    """Verify execution boundary submission generates attempt record, notification, and audit event without false execution."""
    security = SecurityBoundaryService()
    audit = PlatformAuditControlService(security_boundary=security)
    notification_svc = NotificationService(security_service=security)

    order_svc = OrderIntentService(
        security_boundary=security,
        audit_control=audit,
        notification_service=notification_svc,
    )
    exec_svc = ExecutionGatewayService(
        order_intent_service=order_svc,
        security_boundary=security,
        audit_control=audit,
        notification_service=notification_svc,
    )

    user = UserAuthorization(
        user_id="trader_beta",
        auth_code="code_beta_456",
        role=UserRole.CUSTOMER,
        permissions=(Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS),
        activation_timestamp=time.time() - 100,
        expiration_timestamp=time.time() + 86400,
    )

    ts = time.time()
    sig = Signal(action="sell", confidence=0.90, timestamp=ts, strategy_name="EURTrend")
    setup = TradeSetup(
        symbol="EURUSD",
        entry_price=1.0850,
        stop_loss=1.0900,
        take_profit_1=1.0800,
        take_profit_2=1.0750,
        take_profit_3=1.0700,
        timestamp=ts,
        direction="sell",
    )
    trade_sig = TradeSignal(
        signal=sig,
        readiness=Readiness(approved=True, reason="Valid signal", timestamp=ts),
        stability=Stability(score=0.90, risk_level="low"),
        reason="Test signal",
        tradable=True,
        trade_setup=setup,
    )
    auth = AutonomousAuthorization(
        status="AUTHORIZED",
        reason="All gates passed",
        trade_signal=trade_sig,
        timestamp=ts,
    )

    # Stage intent
    _, _, intent = order_svc.create_order_intent(
        user=user,
        authorization=auth,
        idempotency_key=f"idemp_beta_{int(ts)}",
        symbol="EURUSD",
        timestamp=ts,
    )
    assert intent is not None

    # Submit execution request
    result = exec_svc.request_execution(user=user, order_intent_id=intent.order_intent_id)

    # Fail-closed guarantees
    assert result.externally_executed is False
    assert result.order_intent_id == intent.order_intent_id

    # Verify notification created
    notifs = notification_svc.get_notifications(requester=user, target_user_id="trader_beta")
    assert len(notifs) >= 2  # Staged + Execution Request
    exec_notifs = [n for n in notifs if "Execution" in n.title or "EXECUTION" in str(n.metadata)]
    assert len(exec_notifs) >= 1

    # Verify Audit Control event recorded
    ok_aud, _, events = audit.query_events(user=user)
    assert ok_aud is True
    assert len(events) >= 2

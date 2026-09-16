"""Tests for Platform Operational Control Plane & Audit Service."""

import time
import pytest

from src.platform.domain.audit_control import (
    AuditCategory,
    AuditEventSeverity,
    AuditQueryFilter,
    OperationalLifecycleState,
)
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.security import SecurityBoundaryService


@pytest.fixture
def security_service():
    return SecurityBoundaryService()


@pytest.fixture
def audit_service(security_service):
    return PlatformAuditControlService(security_boundary=security_service)


@pytest.fixture
def admin_user():
    return UserAuthorization(
        user_id="admin_123",
        auth_code="admin_code",
        role=UserRole.ADMIN,
        permissions={Permission.ADMIN_ALL},
    )


@pytest.fixture
def normal_user():
    return UserAuthorization(
        user_id="user_456",
        auth_code="user_code",
        role=UserRole.USER,
        permissions={Permission.READ_SIGNALS},
    )


def test_record_and_query_events_success(audit_service, admin_user):
    event = audit_service.record_event(
        user_id="user_456",
        category=AuditCategory.SIGNAL_INTAKE,
        event_type="SIGNAL_RECEIVED",
        lifecycle_state=OperationalLifecycleState.VALIDATED,
        action="PROCESS_SIGNAL",
        outcome="SUCCESS",
        severity=AuditEventSeverity.INFO,
        resource_id="sig_001",
        correlation_id="corr-100",
        details="Received XAUUSD signal from Project 1",
    )

    assert event.event_id is not None
    assert event.user_id == "user_456"
    assert event.category == AuditCategory.SIGNAL_INTAKE

    success, msg, events = audit_service.query_events(user=admin_user)
    assert success is True
    assert len(events) >= 3  # baseline seeded events + new event
    found = [e for e in events if e.event_id == event.event_id]
    assert len(found) == 1


def test_user_isolation_enforcement(audit_service, normal_user, admin_user):
    audit_service.record_event(
        user_id="user_999",
        category=AuditCategory.SECURITY_AUTHORIZATION,
        event_type="LOGIN_ATTEMPT",
        lifecycle_state=OperationalLifecycleState.COMPLETED,
        action="USER_LOGIN",
        outcome="SUCCESS",
    )

    # Normal user query should only get system events or their own events
    success, msg, events = audit_service.query_events(user=normal_user)
    assert success is True
    for e in events:
        assert e.user_id in ("system", "user_456")

    # Admin query gets all events including user_999
    success_admin, msg_admin, events_admin = audit_service.query_events(user=admin_user)
    assert success_admin is True
    assert any(e.user_id == "user_999" for e in events_admin)


def test_unauthenticated_access_denied(audit_service):
    success, msg, events = audit_service.query_events(user=None)
    assert success is False
    assert "Unauthorized" in msg
    assert len(events) == 0


def test_sanitization_of_sensitive_data(audit_service, admin_user):
    event = audit_service.record_event(
        user_id="admin_123",
        category=AuditCategory.STRATEGY_VALIDATION,
        event_type="STRATEGY_CHECK",
        lifecycle_state=OperationalLifecycleState.PROCESSING,
        action="EVALUATE_STRATEGY api_key=supersecret123",
        outcome="SUCCESS",
        details="Executing with token=abc12345678",
        metadata={
            "api_key": "secret_key_value",
            "indicator_logic": "secret_formula",
            "strategy_params": "hidden_param",
            "public_metric": 42,
        },
    )

    assert "[REDACTED]" in event.action
    assert "[REDACTED]" in event.details
    assert event.metadata.get("api_key") == "[REDACTED]" or "api_key" not in event.metadata
    assert "indicator_logic" not in event.metadata
    assert event.metadata.get("public_metric") == 42


def test_get_control_summary(audit_service, admin_user):
    audit_service.record_event(
        user_id="system",
        category=AuditCategory.NOTIFICATION_DISPATCH,
        event_type="DISPATCH_FAILED",
        lifecycle_state=OperationalLifecycleState.FAILED,
        action="SEND_TELEGRAM",
        outcome="FAILURE",
        severity=AuditEventSeverity.ERROR,
    )

    success, msg, summary = audit_service.get_control_summary(user=admin_user)
    assert success is True
    assert summary is not None
    assert summary.total_events >= 3
    assert summary.failed_events_count >= 1
    assert "NOTIFICATION_DISPATCH" in summary.events_by_category

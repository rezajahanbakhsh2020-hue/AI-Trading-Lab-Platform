"""Integration and Hardening Test Suite for Project 1 Integration Gateway & Application Flow.

Verifies end-to-end operational integration hardening:
- Ingestion contract validation (supported vs unsupported schema/version)
- Authorization and user/tenant workspace isolation (Customer vs Admin, IDOR prevention)
- Idempotent replay protection
- Correlation ID propagation
- Canonical NotificationEvent creation
- Audit logging & OperationalFailureRecord tracking
- Secret sanitization across gateway outputs and diagnostics
- HostSnapshot payload integration with project1Gateway summary
"""

import time
import pytest
from src.platform.adapters.project1_repository import FileBackedProject1IntegrationRepository
from src.platform.domain.audit_control import AuditCategory, AuditEventSeverity
from src.platform.domain.security import UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.notification import NotificationService
from src.platform.services.project1_gateway import Project1IntegrationGatewayService
from src.platform.services.project1_presenter import Project1SignalPresenter
from src.platform.adapters.project1_adapter import DisconnectedProject1Adapter


@pytest.fixture
def test_users():
    customer1 = UserAuthorization(
        user_id="cust_001",
        auth_code="auth_code_001",
        role=UserRole.CUSTOMER,
        activation_timestamp=time.time() - 100,
        expiration_timestamp=time.time() + 86400,
        allowed_symbols=("XAUUSD", "EURUSD"),
    )
    customer2 = UserAuthorization(
        user_id="cust_002",
        auth_code="auth_code_002",
        role=UserRole.CUSTOMER,
        activation_timestamp=time.time() - 100,
        expiration_timestamp=time.time() + 86400,
        allowed_symbols=("XAUUSD",),
    )
    admin_user = UserAuthorization(
        user_id="admin_001",
        auth_code="auth_code_admin",
        role=UserRole.ADMIN,
        activation_timestamp=time.time() - 100,
        expiration_timestamp=time.time() + 86400,
        is_permanent_admin=True,
    )
    return {"cust1": customer1, "cust2": customer2, "admin": admin_user}


@pytest.fixture
def gateway_setup(tmp_path):
    storage_path = str(tmp_path / "p1_integration_test.json")
    audit = PlatformAuditControlService()
    repo = FileBackedProject1IntegrationRepository(storage_filepath=storage_path, audit_control=audit)
    notif = NotificationService()
    gateway = Project1IntegrationGatewayService(
        repository=repo,
        audit_control=audit,
        notification_service=notif,
    )
    presenter = Project1SignalPresenter(
        port=DisconnectedProject1Adapter(),
        audit_control_service=audit,
        gateway_service=gateway,
    )
    return {
        "repo": repo,
        "audit": audit,
        "notif": notif,
        "gateway": gateway,
        "presenter": presenter,
    }


def test_valid_ingestion_end_to_end_flow(gateway_setup, test_users):
    gw = gateway_setup["gateway"]
    audit = gateway_setup["audit"]
    notif = gateway_setup["notif"]
    user = test_users["cust1"]

    payload = {
        "integration_id": "int_xauusd_1",
        "signal_id": "sig_xauusd_100",
        "symbol": "XAUUSD",
        "signal_type": "buy",
        "timestamp": time.time(),
        "contract_version": "1.0",
        "entry_price": 2650.0,
        "stop_loss": 2635.0,
        "take_profit_1": 2670.0,
        "confidence": 0.85,
        "strategy_name": "GoldStrategy",
        "secret_token_key": "MUST_BE_REDACTED_SECRET",
    }

    res = gw.ingest_signal_payload(user=user, payload=payload)
    assert res["success"] is True
    assert res["status"] == "INGESTED"
    assert "correlation_id" in res
    assert res["correlation_id"].startswith("p1_corr_")

    # Verify secret is redacted in returned record
    assert "secret_token_key" not in res["record"] or res["record"]["secret_token_key"] == "[REDACTED]"

    # Verify audit event recorded
    ok, msg, events = audit.query_events(user=user)
    assert ok is True
    ingest_events = [e for e in events if e.event_type == "SIGNAL_INGESTED"]
    assert len(ingest_events) == 1
    assert ingest_events[0].resource_id == "sig_xauusd_100"

    # Verify notification created
    notifs = notif.get_notifications(requester=user, target_user_id=user.user_id)
    assert len(notifs) == 1
    assert "XAUUSD" in notifs[0].title


def test_unsupported_contract_version_and_failure_record(gateway_setup, test_users):
    gw = gateway_setup["gateway"]
    audit = gateway_setup["audit"]
    user = test_users["cust1"]

    invalid_payload = {
        "integration_id": "int_bad_ver",
        "signal_id": "sig_bad_ver",
        "symbol": "XAUUSD",
        "signal_type": "buy",
        "timestamp": time.time(),
        "contract_version": "99.0",  # Unsupported contract version
    }

    res = gw.ingest_signal_payload(user=user, payload=invalid_payload)
    assert res["success"] is False
    assert res["error_code"] == "UNSUPPORTED_CONTRACT_VERSION"
    assert "Unsupported contract version" in res["message"]

    # Verify operational failure was recorded
    ok, msg, failures = audit.query_failures(user=test_users["admin"])
    assert ok is True
    ver_failures = [f for f in failures if f.error_type == "UNSUPPORTED_CONTRACT_VERSION"]
    assert len(ver_failures) == 1
    assert ver_failures[0].user_id == user.user_id


def test_idempotent_replay_handling(gateway_setup, test_users):
    gw = gateway_setup["gateway"]
    user = test_users["cust1"]

    payload = {
        "integration_id": "int_idemp_1",
        "signal_id": "sig_idemp_1",
        "symbol": "EURUSD",
        "signal_type": "sell",
        "timestamp": time.time(),
        "contract_version": "1.0",
    }

    res1 = gw.ingest_signal_payload(user=user, payload=payload)
    assert res1["success"] is True
    assert res1["status"] == "INGESTED"

    # Second ingestion attempt with same signal_id
    res2 = gw.ingest_signal_payload(user=user, payload=payload)
    assert res2["success"] is True
    assert res2["status"] == "DUPLICATE_ACCEPTED"
    assert res2["correlation_id"] == res1["correlation_id"]


def test_cross_user_idor_prevention(gateway_setup, test_users):
    gw = gateway_setup["gateway"]
    audit = gateway_setup["audit"]
    user1 = test_users["cust1"]
    user2 = test_users["cust2"]

    payload = {
        "integration_id": "int_idor_1",
        "signal_id": "sig_idor_1",
        "symbol": "XAUUSD",
        "signal_type": "buy",
        "timestamp": time.time(),
        "contract_version": "1.0",
        "user_id": user2.user_id,  # Cust1 attempting to target Cust2
    }

    res = gw.ingest_signal_payload(user=user1, payload=payload)
    assert res["success"] is False
    assert res["error_code"] == "FORBIDDEN_USER_MISMATCH"

    # Verify IDOR incident failure logged
    ok, msg, failures = audit.query_failures(user=test_users["admin"])
    assert ok is True
    idor_fails = [f for f in failures if f.error_type == "FORBIDDEN_USER_MISMATCH"]
    assert len(idor_fails) == 1


def test_host_snapshot_project1_gateway_summary_integration(gateway_setup, test_users):
    gw = gateway_setup["gateway"]
    presenter = gateway_setup["presenter"]
    user = test_users["cust1"]

    gw.ingest_signal_payload(
        user=user,
        payload={
            "integration_id": "int_snap_1",
            "signal_id": "sig_snap_1",
            "symbol": "XAUUSD",
            "signal_type": "buy",
            "timestamp": time.time(),
            "contract_version": "1.0",
        },
    )

    snapshot = presenter.build_host_snapshot(user=user)
    assert "project1Gateway" in snapshot
    gw_summary = snapshot["project1Gateway"]
    assert gw_summary["connected"] is True
    assert gw_summary["contractVersion"] == "1.0"
    assert gw_summary["ingestedRecordsCount"] == 1
    assert len(gw_summary["recentRecords"]) == 1

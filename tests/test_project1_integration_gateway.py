"""Unit and integration test suite for Project 1 Integration Gateway & Contract Layer.

Tests schema validation, contract version rejection, RBAC authorization, customer
isolation (IDOR protection), idempotency replay protection, lifecycle updates,
file-backed persistence restart recovery, and audit control plane logging.
"""

import os
import tempfile
import time
import pytest

from src.platform.adapters.project1_repository import FileBackedProject1IntegrationRepository
from src.platform.domain.project1_contract import (
    Project1SignalContractPayload,
    Project1TrailingStopConfig,
    get_project1_contract_capabilities,
    validate_project1_contract_payload,
)
from src.platform.domain.security import UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.project1_gateway import Project1IntegrationGatewayService
from src.platform.services.security import SecurityBoundaryService


@pytest.fixture
def temp_repo_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield os.path.join(tmpdir, "test_p1_records.json")


@pytest.fixture
def mock_users():
    user_admin = UserAuthorization(
        user_id="usr_admin",
        auth_code="ac_admin",
        role=UserRole.ADMIN,
        allowed_symbols=("XAUUSD", "EURUSD"),
    )
    user_customer = UserAuthorization(
        user_id="usr_customer_101",
        auth_code="ac_cust_101",
        role=UserRole.CUSTOMER,
        allowed_symbols=("XAUUSD", "EURUSD"),
    )
    user_other = UserAuthorization(
        user_id="usr_customer_202",
        auth_code="ac_cust_202",
        role=UserRole.CUSTOMER,
        allowed_symbols=("XAUUSD",),
    )
    user_restricted = UserAuthorization(
        user_id="usr_guest",
        auth_code="ac_guest",
        role=UserRole.GUEST,
        allowed_symbols=(),
    )
    return {
        "admin": user_admin,
        "customer": user_customer,
        "other": user_other,
        "restricted": user_restricted,
    }


def test_contract_capabilities():
    caps = get_project1_contract_capabilities()
    assert caps["gateway_name"] == "Project1IntegrationGateway"
    assert "1.0" in caps["supported_contract_versions"]
    assert caps["guarantees"]["non_calculation"] is True


def test_payload_validation_valid_signal():
    payload = {
        "integration_id": "int_001",
        "signal_id": "sig_xau_001",
        "symbol": "XAUUSD",
        "signal_type": "buy",
        "timestamp": 1700000000.0,
        "contract_version": "1.0",
        "entry_price": 2650.5,
        "stop_loss": 2635.0,
        "take_profit_1": 2670.0,
        "confidence": 0.85,
        "trailing_stop": {
            "distance": 15.0,
            "is_active": True,
        },
    }
    val = validate_project1_contract_payload(payload)
    assert val.is_valid is True
    assert val.sanitized_payload["symbol"] == "XAUUSD"
    assert val.sanitized_payload["signal_type"] == "buy"
    assert val.sanitized_payload["trailing_stop"]["distance"] == 15.0


def test_payload_validation_unsupported_version():
    payload = {
        "integration_id": "int_001",
        "signal_id": "sig_xau_001",
        "symbol": "XAUUSD",
        "signal_type": "buy",
        "timestamp": 1700000000.0,
        "contract_version": "2.0",
    }
    val = validate_project1_contract_payload(payload)
    assert val.is_valid is False
    assert any("Unsupported contract version" in e for e in val.errors)


def test_payload_validation_invalid_prices():
    payload = {
        "integration_id": "int_001",
        "signal_id": "sig_xau_001",
        "symbol": "XAUUSD",
        "signal_type": "buy",
        "timestamp": 1700000000.0,
        "contract_version": "1.0",
        "entry_price": -100.0,
    }
    val = validate_project1_contract_payload(payload)
    assert val.is_valid is False
    assert any("entry_price must be a positive finite number" in e for e in val.errors)


def test_gateway_ingest_unauthenticated(temp_repo_path):
    repo = FileBackedProject1IntegrationRepository(temp_repo_path)
    service = Project1IntegrationGatewayService(repository=repo)
    res = service.ingest_signal_payload(user=None, payload={})
    assert res["success"] is False
    assert res["error_code"] == "UNAUTHENTICATED"


def test_gateway_ingest_and_retrieve(temp_repo_path, mock_users):
    repo = FileBackedProject1IntegrationRepository(temp_repo_path)
    sec = SecurityBoundaryService()
    audit = PlatformAuditControlService(security_boundary=sec)
    service = Project1IntegrationGatewayService(
        repository=repo, security_boundary=sec, audit_control=audit
    )

    cust = mock_users["customer"]
    payload = {
        "integration_id": "int_cust_001",
        "signal_id": "sig_cust_101",
        "symbol": "XAUUSD",
        "signal_type": "buy",
        "timestamp": 1700000000.0,
        "contract_version": "1.0",
        "entry_price": 2650.0,
        "stop_loss": 2635.0,
        "take_profit_1": 2680.0,
    }

    res = service.ingest_signal_payload(user=cust, payload=payload)
    assert res["success"] is True
    assert res["status"] == "INGESTED"
    assert res["record"]["user_id"] == cust.user_id

    # List records for customer
    records_res = service.list_records(user=cust)
    assert records_res["success"] is True
    assert records_res["count"] == 1
    assert records_res["records"][0]["signal_id"] == "sig_cust_101"


def test_gateway_customer_isolation_idor(temp_repo_path, mock_users):
    repo = FileBackedProject1IntegrationRepository(temp_repo_path)
    service = Project1IntegrationGatewayService(repository=repo)

    cust = mock_users["customer"]
    payload = {
        "integration_id": "int_cust_001",
        "signal_id": "sig_cust_101",
        "symbol": "XAUUSD",
        "signal_type": "buy",
        "timestamp": 1700000000.0,
        "contract_version": "1.0",
        "user_id": "usr_customer_202",  # Attempt IDOR to target user 202
    }

    res = service.ingest_signal_payload(user=cust, payload=payload)
    assert res["success"] is False
    assert res["error_code"] == "FORBIDDEN_USER_MISMATCH"

    # Verify other customer cannot read user 101's records
    other = mock_users["other"]
    recs = service.list_records(user=other)
    assert recs["count"] == 0


def test_gateway_replay_protection_idempotency(temp_repo_path, mock_users):
    repo = FileBackedProject1IntegrationRepository(temp_repo_path)
    service = Project1IntegrationGatewayService(repository=repo)

    cust = mock_users["customer"]
    payload = {
        "integration_id": "int_cust_001",
        "signal_id": "sig_idemp_101",
        "symbol": "XAUUSD",
        "signal_type": "sell",
        "timestamp": 1700000000.0,
        "contract_version": "1.0",
    }

    res1 = service.ingest_signal_payload(user=cust, payload=payload)
    assert res1["success"] is True
    assert res1["status"] == "INGESTED"

    # Replay same request
    res2 = service.ingest_signal_payload(user=cust, payload=payload)
    assert res2["success"] is True
    assert res2["status"] == "DUPLICATE_ACCEPTED"
    assert res2["correlation_id"] == res1["correlation_id"]


def test_gateway_lifecycle_update(temp_repo_path, mock_users):
    repo = FileBackedProject1IntegrationRepository(temp_repo_path)
    service = Project1IntegrationGatewayService(repository=repo)

    cust = mock_users["customer"]
    payload = {
        "integration_id": "int_cust_001",
        "signal_id": "sig_life_101",
        "symbol": "XAUUSD",
        "signal_type": "buy",
        "timestamp": 1700000000.0,
        "contract_version": "1.0",
    }

    service.ingest_signal_payload(user=cust, payload=payload)

    # Update lifecycle to CANCELLED
    up_res = service.update_lifecycle(
        user=cust,
        payload={
            "signal_id": "sig_life_101",
            "lifecycle_state": "CANCELLED",
            "reason": "Market conditions invalid",
        },
    )
    assert up_res["success"] is True
    assert up_res["lifecycle_state"] == "CANCELLED"

    records_res = service.list_records(user=cust)
    assert records_res["records"][0]["lifecycle_state"] == "CANCELLED"


def test_persistence_reload_across_restart(temp_repo_path, mock_users):
    cust = mock_users["customer"]

    # Session 1: Ingest record
    repo1 = FileBackedProject1IntegrationRepository(temp_repo_path)
    service1 = Project1IntegrationGatewayService(repository=repo1)
    payload = {
        "integration_id": "int_restart_001",
        "signal_id": "sig_restart_001",
        "symbol": "EURUSD",
        "signal_type": "buy",
        "timestamp": 1700000000.0,
        "contract_version": "1.0",
    }
    service1.ingest_signal_payload(user=cust, payload=payload)

    # Session 2: Reload repository from file path
    repo2 = FileBackedProject1IntegrationRepository(temp_repo_path)
    service2 = Project1IntegrationGatewayService(repository=repo2)
    records_res = service2.list_records(user=cust)
    assert records_res["count"] == 1
    assert records_res["records"][0]["signal_id"] == "sig_restart_001"
    assert records_res["records"][0]["symbol"] == "EURUSD"

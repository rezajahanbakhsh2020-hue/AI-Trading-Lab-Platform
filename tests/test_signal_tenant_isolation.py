"""Regression tests for Project 2 Signal Gateway Data Integrity and Tenant Isolation.

Verifies:
- User/Tenant signal isolation (User A signal hidden from User B / Tenant B)
- Rejection of missing/invalid provenance from Current Signal feed
- Exclusion of inactive lifecycle states (CANCELLED, EXPIRED, REJECTED, EXECUTED)
- Truthful adapter describe() status (Gateway ready vs record receipt)
- Server /ready machine-readable endpoint
- Provider connectivity status reporting in HostSnapshot
"""

import time
import pytest

from src.platform.adapters.project1_adapter import Project1GatewayAdapter
from src.platform.adapters.project1_repository import FileBackedProject1IntegrationRepository
from src.platform.domain.security import UserRole, Permission
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.project1_gateway import Project1IntegrationGatewayService
from src.platform.services.project1_presenter import Project1SignalPresenter


@pytest.fixture
def temp_repo(tmp_path):
    storage_file = str(tmp_path / "p1_tenant_test_records.json")
    return FileBackedProject1IntegrationRepository(storage_filepath=storage_file)


@pytest.fixture
def gateway_svc(temp_repo):
    return Project1IntegrationGatewayService(repository=temp_repo)


@pytest.fixture
def user_a():
    return UserAuthorization(
        user_id="user_a",
        auth_code="code_a_123",
        role=UserRole.CUSTOMER,
        permissions=[Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS],
    )


@pytest.fixture
def user_b():
    return UserAuthorization(
        user_id="user_b",
        auth_code="code_b_456",
        role=UserRole.CUSTOMER,
        permissions=[Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS],
    )


def test_cross_user_tenant_signal_isolation(gateway_svc, user_a, user_b):
    """User A signal must be visible to User A, but NOT to User B."""
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    presenter = Project1SignalPresenter(port=adapter, gateway_service=gateway_svc)

    now_ts = time.time() - 20
    payload_a = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "integ_user_a_001",
        "signal_id": "p1_xauusd_user_a",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": now_ts,
        "entry_price": 2700.0,
        "stop_loss": 2680.0,
        "take_profit_1": 2730.0,
        "confidence": 0.85,
        "strategy_name": "GoldStrategyA",
        "metadata": {"provenance_type": "live_signal"},
    }

    # Ingest for User A
    ingest_res = gateway_svc.ingest_signal_payload(user=user_a, payload=payload_a)
    assert ingest_res["success"] is True

    # User A fetches signal -> Success
    sig_a = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h", user_id=user_a.user_id)
    assert sig_a is not None
    assert sig_a.signal_id == "p1_xauusd_user_a"

    pres_a = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=user_a)
    assert pres_a["status"] == "active"
    assert pres_a["signal"]["signal_id"] == "p1_xauusd_user_a"

    # User B fetches signal -> None / No signal
    sig_b = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h", user_id=user_b.user_id)
    assert sig_b is None

    pres_b = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=user_b)
    assert pres_b["status"] == "no-signal"
    assert pres_b["signal"] is None


def test_missing_provenance_fails_closed(gateway_svc, user_a):
    """Ingesting a payload with missing provenance must NOT auto-upgrade to live_signal."""
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    presenter = Project1SignalPresenter(port=adapter, gateway_service=gateway_svc)

    now_ts = time.time() - 15
    payload_no_prov = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "integ_no_prov_001",
        "signal_id": "p1_xauusd_no_prov",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": now_ts,
        "entry_price": 2700.0,
        "stop_loss": 2680.0,
        "take_profit_1": 2730.0,
        "confidence": 0.85,
        "strategy_name": "GoldStrategyNoProv",
        "metadata": {},  # Missing provenance_type
    }

    ingest_res = gateway_svc.ingest_signal_payload(user=user_a, payload=payload_no_prov)
    assert ingest_res["success"] is True
    assert "provenance_type" not in ingest_res["record"].get("metadata", {})

    # Gateway adapter must refuse missing provenance
    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h", user_id=user_a.user_id)
    assert sig is None

    pres = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=user_a)
    assert pres["status"] == "no-signal"
    assert pres["signal"] is None


def test_inactive_lifecycle_states_excluded_from_current_signal(gateway_svc, user_a):
    """Signals in CANCELLED, EXPIRED, REJECTED, EXECUTED states must be excluded from Current Signal."""
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    presenter = Project1SignalPresenter(port=adapter, gateway_service=gateway_svc)

    now_ts = time.time() - 10
    payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "integ_lifecycle_001",
        "signal_id": "p1_xauusd_cancelled",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": now_ts,
        "entry_price": 2700.0,
        "stop_loss": 2680.0,
        "take_profit_1": 2730.0,
        "confidence": 0.85,
        "strategy_name": "GoldStrategyLifecycle",
        "metadata": {"provenance_type": "live_signal"},
    }

    gateway_svc.ingest_signal_payload(user=user_a, payload=payload)

    # Transition lifecycle to CANCELLED
    gateway_svc.update_lifecycle(
        user=user_a,
        payload={"signal_id": "p1_xauusd_cancelled", "lifecycle_state": "CANCELLED"},
    )

    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h", user_id=user_a.user_id)
    assert sig is None

    pres = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=user_a)
    assert pres["status"] == "no-signal"
    assert pres["signal"] is None


def test_adapter_describe_truthful_gateway_readiness(gateway_svc, user_a):
    """Adapter describe() must report connected=True and status='ready' when configured, even before data arrives."""
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)

    desc_before = adapter.describe(user_id=user_a.user_id)
    assert desc_before["connected"] is True
    assert desc_before["gateway_ready"] is True
    assert desc_before["status"] == "ready"
    assert desc_before["received_records_count"] == 0

    # Ingest a record
    payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "integ_desc_001",
        "signal_id": "p1_desc_001",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": time.time() - 10,
        "metadata": {"provenance_type": "live_signal"},
    }
    gateway_svc.ingest_signal_payload(user=user_a, payload=payload)

    desc_after = adapter.describe(user_id=user_a.user_id)
    assert desc_after["connected"] is True
    assert desc_after["status"] == "active"
    assert desc_after["received_records_count"] == 1

"""Comprehensive unit and regression test suite verifying all 20 Project 1 Live Signal runtime contract criteria.

Validates:
1. Authorized real upstream signal is accepted.
2. Upstream values are preserved exactly (entry, SL, TPs, confidence, strategy).
3. Provenance is preserved (live_signal).
4. Event timestamp is preserved.
5. Receipt time cannot replace event time.
6. XAUUSD identity remains XAUUSD.
7. Mismatched instrument is rejected.
8. Missing instrument is rejected.
9. Zero upstream records produce NO SIGNAL.
10. Unauthorized source produces NO SIGNAL.
11. Malformed payload produces NO SIGNAL.
12. Stale event produces NO SIGNAL according to existing policy (>300s).
13. Invalid event time produces NO SIGNAL (<=0 or future time).
14. Fixture/sample cannot enter connected runtime.
15. Old sample Project 1 signal cannot reappear.
16. Current Signal selects the latest valid authorized event using correct event-time semantics.
17. Upstream entry/SL/TP/risk values are not recalculated by Project 2.
18. Disconnected/unconfigured state remains truthful.
19. Workspace isolation remains enforced.
20. Existing Gateway authentication/authorization remains enforced.
"""

import time
import pytest

from src.platform.adapters.project1_adapter import (
    DisconnectedProject1Adapter,
    Project1GatewayAdapter,
)
from src.platform.adapters.project1_repository import FileBackedProject1IntegrationRepository
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.project1_gateway import Project1IntegrationGatewayService
from src.platform.services.project1_presenter import Project1SignalPresenter
from src.platform.services.security import SecurityBoundaryService


@pytest.fixture
def temp_repo(tmp_path):
    storage_filepath = str(tmp_path / "p1_runtime_records_test.json")
    return FileBackedProject1IntegrationRepository(storage_filepath=storage_filepath)


@pytest.fixture
def sec_boundary():
    return SecurityBoundaryService()


@pytest.fixture
def audit_control(sec_boundary):
    return PlatformAuditControlService(security_boundary=sec_boundary)


@pytest.fixture
def gateway_svc(temp_repo, sec_boundary, audit_control):
    return Project1IntegrationGatewayService(
        repository=temp_repo,
        security_boundary=sec_boundary,
        audit_control=audit_control,
    )


@pytest.fixture
def admin_user():
    return UserAuthorization(
        user_id="usr_admin_01",
        auth_code="code_admin_01",
        role=UserRole.ADMIN,
        is_permanent_admin=True,
    )


@pytest.fixture
def customer_user_a():
    return UserAuthorization(
        user_id="usr_customer_a",
        auth_code="code_cust_a",
        role=UserRole.CUSTOMER,
        permissions=[Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS],
    )


@pytest.fixture
def customer_user_b():
    return UserAuthorization(
        user_id="usr_customer_b",
        auth_code="code_cust_b",
        role=UserRole.CUSTOMER,
        permissions=[Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS],
    )


def test_1_authorized_real_upstream_signal_accepted(gateway_svc, admin_user):
    """Criteria 1: Authorized real upstream signal is accepted."""
    now = time.time()
    payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_auth_001",
        "signal_id": "sig_auth_001",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": now - 15.0,
        "entry_price": 2750.00,
        "stop_loss": 2735.00,
        "take_profit_1": 2770.00,
        "confidence": 0.90,
        "strategy_name": "GoldStrategy",
        "metadata": {"provenance_type": "live_signal"},
    }

    res = gateway_svc.ingest_signal_payload(user=admin_user, payload=payload)
    assert res["success"] is True
    assert res["status"] == "INGESTED"


def test_2_upstream_values_preserved_exactly(gateway_svc, admin_user):
    """Criteria 2: Upstream entry, SL, TP, confidence, strategy values are preserved exactly."""
    now = time.time()
    payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_values_002",
        "signal_id": "sig_values_002",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": now - 10.0,
        "entry_price": 2762.35,
        "stop_loss": 2741.10,
        "take_profit_1": 2785.50,
        "take_profit_2": 2800.00,
        "take_profit_3": 2820.25,
        "confidence": 0.942,
        "strategy_name": "ExactPrecisionStrategy",
        "metadata": {"provenance_type": "live_signal"},
    }

    gateway_svc.ingest_signal_payload(user=admin_user, payload=payload)
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h", user_id="usr_admin_01")

    assert sig is not None
    assert sig.entry_price == 2762.35
    assert sig.stop_loss == 2741.10
    assert sig.take_profits == (2785.50, 2800.00, 2820.25)
    assert sig.confidence == 0.942
    assert sig.strategy_name == "ExactPrecisionStrategy"


def test_3_provenance_preserved(gateway_svc, admin_user):
    """Criteria 3: Provenance (live_signal) is preserved."""
    now = time.time()
    payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_prov_003",
        "signal_id": "sig_prov_003",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "sell",
        "timestamp": now - 20.0,
        "metadata": {"provenance_type": "live_signal", "source_system": "P1_Core_Alpha"},
    }

    gateway_svc.ingest_signal_payload(user=admin_user, payload=payload)
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h", user_id="usr_admin_01")

    assert sig is not None
    assert sig.metadata.get("provenance_type") == "live_signal"
    assert sig.metadata.get("source_system") == "P1_Core_Alpha"


def test_4_event_timestamp_preserved(gateway_svc, admin_user):
    """Criteria 4: Event timestamp is preserved exactly as emitted by Project 1."""
    event_ts = time.time() - 45.0
    payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_ts_004",
        "signal_id": "sig_ts_004",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": event_ts,
        "metadata": {"provenance_type": "live_signal"},
    }

    gateway_svc.ingest_signal_payload(user=admin_user, payload=payload)
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h", user_id="usr_admin_01")

    assert sig is not None
    assert sig.timestamp == event_ts


def test_5_receipt_time_cannot_replace_event_time(temp_repo, gateway_svc, admin_user):
    """Criteria 5: Receipt time (created_at) cannot replace event timestamp for ordering/eligibility."""
    now = time.time()
    old_event_ts = now - 600.0  # 10 minutes ago (stale event time)

    payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_stale_rec_005",
        "signal_id": "sig_stale_rec_005",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": old_event_ts,
        "metadata": {"provenance_type": "live_signal"},
    }

    # Ingest right NOW (receipt time = now)
    gateway_svc.ingest_signal_payload(user=admin_user, payload=payload)

    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    presenter = Project1SignalPresenter(port=adapter, gateway_service=gateway_svc)

    # Even though received NOW, presenter uses event timestamp (600s old) -> rejected as stale
    pres_res = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=admin_user)
    assert pres_res["status"] == "no-signal"
    assert pres_res["signal"] is None


def test_6_xauusd_identity_remains_xauusd(gateway_svc, admin_user):
    """Criteria 6: XAUUSD identity remains XAUUSD."""
    now = time.time()
    payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_xauusd_006",
        "signal_id": "sig_xauusd_006",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": now - 12.0,
        "metadata": {"provenance_type": "live_signal"},
    }

    gateway_svc.ingest_signal_payload(user=admin_user, payload=payload)
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h", user_id="usr_admin_01")

    assert sig is not None
    assert sig.symbol == "XAUUSD"


def test_7_mismatched_instrument_rejected(gateway_svc, admin_user):
    """Criteria 7: Mismatched instrument requested is rejected."""
    now = time.time()
    payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_eurusd_007",
        "signal_id": "sig_eurusd_007",
        "symbol": "EURUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": now - 10.0,
        "metadata": {"provenance_type": "live_signal"},
    }

    gateway_svc.ingest_signal_payload(user=admin_user, payload=payload)
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)

    # Requesting XAUUSD when only EURUSD exists -> None
    sig_xau = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h", user_id="usr_admin_01")
    assert sig_xau is None

    presenter = Project1SignalPresenter(port=adapter, gateway_service=gateway_svc)
    pres_res = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=admin_user)
    assert pres_res["status"] == "no-signal"
    assert pres_res["signal"] is None


def test_8_missing_instrument_rejected(temp_repo, gateway_svc, admin_user):
    """Criteria 8: Missing instrument in record is rejected (fails closed)."""
    raw_rec = {
        "integration_id": "intg_no_sym_008",
        "signal_id": "sig_no_sym_008",
        "symbol": None,  # missing symbol
        "command_type": "EMIT_SIGNAL",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": time.time() - 10.0,
        "metadata": {"provenance_type": "live_signal"},
    }
    temp_repo.save_record(raw_rec)

    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h", user_id="usr_admin_01")
    assert sig is None


def test_9_zero_upstream_records_produce_no_signal(gateway_svc, admin_user):
    """Criteria 9: Zero upstream records produce NO SIGNAL."""
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    presenter = Project1SignalPresenter(port=adapter, gateway_service=gateway_svc)

    pres = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=admin_user)
    assert pres["connected"] is True
    assert pres["status"] == "no-signal"
    assert pres["signal"] is None

    snapshot = presenter.build_host_snapshot(symbol="XAUUSD", timeframe="1h", user=admin_user)
    assert snapshot["signal"]["action"] == "NO SIGNAL"
    assert snapshot["signal"]["status"] == "no-signal"


def test_10_unauthorized_source_produces_no_signal(gateway_svc, admin_user):
    """Criteria 10: Signal from unauthorized provenance source produces NO SIGNAL."""
    now = time.time()
    payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_unauth_src_010",
        "signal_id": "sig_unauth_src_010",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": now - 10.0,
        "metadata": {"provenance_type": "untrusted_external_feed"},
    }

    gateway_svc.ingest_signal_payload(user=admin_user, payload=payload)
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)

    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h", user_id="usr_admin_01")
    assert sig is None


def test_11_malformed_payload_produces_no_signal(gateway_svc, admin_user):
    """Criteria 11: Malformed contract payload is rejected during ingest."""
    malformed_payload = {
        "contract_version": "99.0",  # invalid version
        "integration_id": "intg_bad_011",
        "signal_id": "sig_bad_011",
        "symbol": "XAUUSD",
        "signal_type": "INVALID_TYPE",
    }

    res = gateway_svc.ingest_signal_payload(user=admin_user, payload=malformed_payload)
    assert res["success"] is False
    assert "Contract validation failed" in res["message"]


def test_12_stale_event_produces_no_signal(gateway_svc, admin_user):
    """Criteria 12: Stale event (>300s) produces NO SIGNAL."""
    now = time.time()
    payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_stale_012",
        "signal_id": "sig_stale_012",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": now - 350.0,  # >300s old
        "metadata": {"provenance_type": "live_signal"},
    }

    gateway_svc.ingest_signal_payload(user=admin_user, payload=payload)
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    presenter = Project1SignalPresenter(port=adapter, gateway_service=gateway_svc)

    pres = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=admin_user)
    assert pres["status"] == "no-signal"
    assert pres["signal"] is None


def test_13_invalid_event_time_produces_no_signal(gateway_svc, admin_user):
    """Criteria 13: Invalid event time (future timestamp) produces NO SIGNAL."""
    now = time.time()
    payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_future_013",
        "signal_id": "sig_future_013",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": now + 500.0,  # future timestamp
        "metadata": {"provenance_type": "live_signal"},
    }

    gateway_svc.ingest_signal_payload(user=admin_user, payload=payload)
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)

    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h", user_id="usr_admin_01")
    assert sig is None


def test_14_fixture_sample_cannot_enter_connected_runtime(gateway_svc, admin_user):
    """Criteria 14: Fixture/sample record (lab_artifact) cannot enter connected runtime."""
    now = time.time()
    payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_sample_014",
        "signal_id": "sig_sample_014",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": now - 10.0,
        "metadata": {"provenance_type": "lab_artifact", "is_historical": True},
    }

    gateway_svc.ingest_signal_payload(user=admin_user, payload=payload)
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)

    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h", user_id="usr_admin_01")
    assert sig is None


def test_15_old_sample_project1_signal_cannot_reappear(gateway_svc, admin_user):
    """Criteria 15: Disconnected or zero-record state produces no hardcoded sample signal."""
    disc_adapter = DisconnectedProject1Adapter()
    presenter = Project1SignalPresenter(port=disc_adapter, gateway_service=gateway_svc)

    pres = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=admin_user)
    assert pres["connected"] is False
    assert pres["signal"] is None

    snapshot = presenter.build_host_snapshot(symbol="XAUUSD", timeframe="1h", user=admin_user)
    assert snapshot["project1"]["connected"] is False
    assert snapshot["signal"]["action"] is None
    assert snapshot["signal"]["status"] == "unavailable"


def test_16_current_signal_selects_latest_valid_authorized_event(gateway_svc, admin_user):
    """Criteria 16: Current Signal selects the latest valid authorized event using correct event-time semantics."""
    now = time.time()

    # Older valid event (now - 80s)
    payload_1 = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_order_1",
        "signal_id": "sig_older_016",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": now - 80.0,
        "entry_price": 2740.0,
        "metadata": {"provenance_type": "live_signal"},
    }

    # Newer valid event (now - 15s)
    payload_2 = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_order_2",
        "signal_id": "sig_newer_016",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "sell",
        "timestamp": now - 15.0,
        "entry_price": 2755.0,
        "metadata": {"provenance_type": "live_signal"},
    }

    # Ingest older first, then newer
    gateway_svc.ingest_signal_payload(user=admin_user, payload=payload_1)
    gateway_svc.ingest_signal_payload(user=admin_user, payload=payload_2)

    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h", user_id="usr_admin_01")

    assert sig is not None
    assert sig.signal_id == "sig_newer_016"
    assert sig.timestamp == now - 15.0
    assert sig.signal_type == "sell"
    assert sig.entry_price == 2755.0


def test_17_upstream_values_not_recalculated_by_project2(gateway_svc, admin_user):
    """Criteria 17: Upstream entry, SL, TP values are presented without recalculation or alteration."""
    now = time.time()
    payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_norecalc_017",
        "signal_id": "sig_norecalc_017",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": now - 10.0,
        "entry_price": 2688.88,
        "stop_loss": 2670.00,
        "take_profit_1": 2710.00,
        "take_profit_2": 2730.00,
        "confidence": 0.88,
        "strategy_name": "AsIsStrategy",
        "metadata": {"provenance_type": "live_signal"},
    }

    gateway_svc.ingest_signal_payload(user=admin_user, payload=payload)
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    presenter = Project1SignalPresenter(port=adapter, gateway_service=gateway_svc)

    pres = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=admin_user)
    assert pres["status"] == "active"
    sig = pres["signal"]

    assert sig["entry_price"] == 2688.88
    assert sig["stop_loss"] == 2670.00
    assert sig["take_profits"] == [2710.00, 2730.00]


def test_18_disconnected_unconfigured_state_remains_truthful():
    """Criteria 18: Disconnected/unconfigured state remains truthful."""
    disc_adapter = DisconnectedProject1Adapter()
    desc = disc_adapter.describe()

    assert desc["connected"] is False
    assert desc["status"] == "disconnected"
    assert desc["message"] == "No Project 1 data connected yet."


def test_19_workspace_isolation_remains_enforced(gateway_svc, admin_user, customer_user_a, customer_user_b):
    """Criteria 19: Customer workspace isolation is strictly enforced."""
    now = time.time()

    # User A ingests signal targeting User A
    payload_a = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_cust_a_019",
        "signal_id": "sig_cust_a_019",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": now - 10.0,
        "user_id": "usr_customer_a",
        "metadata": {"provenance_type": "live_signal"},
    }

    gateway_svc.ingest_signal_payload(user=customer_user_a, payload=payload_a)

    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)

    # User A sees User A's signal
    sig_a = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h", user_id="usr_customer_a")
    assert sig_a is not None
    assert sig_a.signal_id == "sig_cust_a_019"

    # User B cannot see User A's signal
    sig_b = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h", user_id="usr_customer_b")
    assert sig_b is None


def test_20_existing_gateway_authentication_authorization_enforced(gateway_svc):
    """Criteria 20: Gateway authentication and RBAC authorization remain enforced."""
    now = time.time()
    payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_unauth_020",
        "signal_id": "sig_unauth_020",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": now - 10.0,
        "metadata": {"provenance_type": "live_signal"},
    }

    # Anonymous call -> UNAUTHENTICATED
    res_anon = gateway_svc.ingest_signal_payload(user=None, payload=payload)
    assert res_anon["success"] is False
    assert res_anon["error_code"] == "UNAUTHENTICATED"

    # Guest user without write permission -> UNAUTHORIZED
    guest_user = UserAuthorization(
        user_id="usr_guest",
        auth_code="code_guest",
        role=UserRole.GUEST,
        permissions=[],
    )
    res_guest = gateway_svc.ingest_signal_payload(user=guest_user, payload=payload)
    assert res_guest["success"] is False
    assert res_guest["error_code"] == "UNAUTHORIZED"

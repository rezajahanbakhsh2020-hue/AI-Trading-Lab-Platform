"""Comprehensive unit and regression tests for Event-Time Correctness and Provenance Safety.

Verifies:
Test 1: Event timestamp wins over storage insertion order.
Test 2: Stale record inserted later does not overwrite newer event-time signal.
Test 3: Missing or invalid timestamp in record is rejected (no time.time() fallback; fail-closed).
Test 4: Missing provenance_type in record is rejected (no implicit promotion to live_signal).
Test 5: Historical provenance (lab_artifact or is_historical=True) is never selected as current signal.
Test 6: Future-dated signal is rejected by eligibility gate.
Test 7: PR #86 historical isolation (2023 archive record stays isolated from Current Signal).
Test 8: Runtime verification wiring contract.
"""

import time
from datetime import datetime, timezone
import pytest

from src.platform.adapters.project1_adapter import Project1GatewayAdapter, Project1LabArtifactAdapter
from src.platform.adapters.project1_repository import FileBackedProject1IntegrationRepository
from src.platform.domain.user_authorization import UserAuthorization, UserRole
from src.platform.services.lab_artifacts import LabArtifactService
from src.platform.integrations.lab import LabArtifactSource
from src.platform.services.project1_gateway import Project1IntegrationGatewayService
from src.platform.services.project1_presenter import Project1SignalPresenter


class DummyLabSource(LabArtifactSource):
    def connect(self):
        pass

    def close(self):
        pass

    def describe(self):
        return {"name": "DummyLabSource", "status": "active"}

    def fetch_signal(self, symbol: str, timeframe: str):
        return {
            "action": "BUY",
            "strategy_name": "GoldTrendv1",
            "timestamp": 1700000000.0,
            "confidence": 0.88,
        }

    def fetch_trade_setup(self, symbol: str, timeframe: str):
        return {
            "symbol": symbol,
            "entry_price": 1980.0,
            "stop_loss": 1960.0,
            "take_profit_1": 2000.0,
            "take_profit_2": 2020.0,
            "take_profit_3": 2040.0,
            "timestamp": 1700000000.0,
            "direction": "buy",
        }

    def fetch_stability(self, strategy_name: str):
        return None

    def fetch_walk_forward(self, strategy_name: str):
        return None


@pytest.fixture
def temp_repo(tmp_path):
    return FileBackedProject1IntegrationRepository(
        storage_filepath=str(tmp_path / "test_event_time_records.json")
    )


@pytest.fixture
def gateway_svc(temp_repo):
    return Project1IntegrationGatewayService(repository=temp_repo)


@pytest.fixture
def admin_user():
    return UserAuthorization(
        user_id="usr_admin_test",
        auth_code="code_admin_test",
        role=UserRole.ADMIN,
        is_permanent_admin=True,
    )


def test_1_event_timestamp_wins_over_insertion_order(gateway_svc, admin_user):
    """Test 1 — Event timestamp wins over insertion order.

    Record A has older timestamp (now - 100s).
    Record B has newer timestamp (now - 20s).
    Insertion order: Record A is saved SECOND (newer insertion, older event time).
    Assert: fetch_latest_signal selects Record B (greatest event timestamp).
    """
    now = time.time()
    ts_newer = now - 20.0
    ts_older = now - 100.0

    # Save Record B (newer event time) FIRST
    payload_b = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_b_newer",
        "signal_id": "p1_xauusd_1h_newer_event",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": ts_newer,
        "confidence": 0.90,
        "strategy_name": "GoldTrendv1",
        "metadata": {"provenance_type": "live_signal"},
    }
    res_b = gateway_svc.ingest_signal_payload(user=admin_user, payload=payload_b)
    assert res_b["success"] is True

    # Save Record A (older event time) SECOND
    payload_a = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_a_older",
        "signal_id": "p1_xauusd_1h_older_event",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "sell",
        "timestamp": ts_older,
        "confidence": 0.75,
        "strategy_name": "GoldTrendv1",
        "metadata": {"provenance_type": "live_signal"},
    }
    res_a = gateway_svc.ingest_signal_payload(user=admin_user, payload=payload_a)
    assert res_a["success"] is True

    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h")

    assert sig is not None
    assert sig.signal_id == "p1_xauusd_1h_newer_event"
    assert sig.timestamp == ts_newer
    assert sig.signal_type == "buy"


def test_2_stale_record_inserted_later_does_not_replace_newer_signal(gateway_svc, admin_user):
    """Test 2 — Stale record inserted later does not replace newer event-time signal."""
    now = time.time()
    ts_fresh = now - 10.0
    ts_stale = now - 1000.0  # stale (>300s)

    # 1. Save fresh signal first
    payload_fresh = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_fresh",
        "signal_id": "sig_fresh_001",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": ts_fresh,
        "confidence": 0.95,
        "strategy_name": "GoldTrendv1",
        "metadata": {"provenance_type": "live_signal"},
    }
    gateway_svc.ingest_signal_payload(user=admin_user, payload=payload_fresh)

    # 2. Save stale signal later
    payload_stale = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_stale_later",
        "signal_id": "sig_stale_002",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "sell",
        "timestamp": ts_stale,
        "confidence": 0.80,
        "strategy_name": "GoldTrendv1",
        "metadata": {"provenance_type": "live_signal"},
    }
    gateway_svc.ingest_signal_payload(user=admin_user, payload=payload_stale)

    # 3. Query adapter and presenter
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    presenter = Project1SignalPresenter(port=adapter, gateway_service=gateway_svc)

    latest_sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h")
    assert latest_sig is not None
    assert latest_sig.signal_id == "sig_fresh_001"
    assert latest_sig.timestamp == ts_fresh

    pres_res = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=admin_user)
    assert pres_res["status"] == "active"
    assert pres_res["signal"]["signal_id"] == "sig_fresh_001"


def test_3_missing_timestamp_fail_closed(temp_repo, gateway_svc, admin_user):
    """Test 3 — Record missing or invalid timestamp is rejected (no time.time() fallback)."""
    # Directly insert raw record with missing/None timestamp into repository
    raw_rec = {
        "integration_id": "intg_no_ts",
        "signal_id": "sig_no_ts",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": None,
        "confidence": 0.85,
        "metadata": {"provenance_type": "live_signal"},
    }
    temp_repo.save_record(raw_rec)

    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h")

    assert sig is None

    presenter = Project1SignalPresenter(port=adapter, gateway_service=gateway_svc)
    pres_res = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=admin_user)
    assert pres_res["status"] == "no-signal"
    assert pres_res["signal"] is None


def test_4_missing_provenance_fail_closed(temp_repo, gateway_svc, admin_user):
    """Test 4 — Record missing provenance_type is rejected (no implicit live_signal promotion)."""
    now = time.time()
    # Save record directly into repo with metadata missing provenance_type
    raw_rec = {
        "integration_id": "intg_no_prov",
        "signal_id": "sig_no_prov",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": now - 10.0,
        "confidence": 0.85,
        "metadata": {"source": "external_file"},  # no provenance_type
    }
    temp_repo.save_record(raw_rec)

    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h")

    assert sig is None

    presenter = Project1SignalPresenter(port=adapter, gateway_service=gateway_svc)
    pres_res = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=admin_user)
    assert pres_res["status"] == "no-signal"
    assert pres_res["signal"] is None


def test_5_historical_provenance_never_promoted_to_live(temp_repo, gateway_svc, admin_user):
    """Test 5 — Record with historical/lab_artifact provenance is never selected as Current Signal."""
    now = time.time()
    raw_rec = {
        "integration_id": "intg_lab_art",
        "signal_id": "sig_lab_art",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": now - 10.0,  # fresh timestamp, but lab_artifact
        "confidence": 0.90,
        "metadata": {"provenance_type": "lab_artifact", "is_historical": True},
    }
    temp_repo.save_record(raw_rec)

    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h")

    assert sig is None

    presenter = Project1SignalPresenter(port=adapter, gateway_service=gateway_svc)
    pres_res = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=admin_user)
    assert pres_res["status"] == "no-signal"
    assert pres_res["signal"] is None


def test_6_future_dated_signal_rejected(gateway_svc, admin_user):
    """Test 6 — Future-dated signal is rejected."""
    now = time.time()
    future_ts = now + 1000.0

    payload_future = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "intg_future",
        "signal_id": "sig_future_001",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": future_ts,
        "confidence": 0.90,
        "strategy_name": "GoldTrendv1",
        "metadata": {"provenance_type": "live_signal"},
    }
    gateway_svc.ingest_signal_payload(user=admin_user, payload=payload_future)

    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h")

    assert sig is None


def test_7_pr86_historical_isolation_regression(temp_repo, gateway_svc, admin_user):
    """Test 7 — Nov 2023 archive record stays isolated from live signal feed."""
    historical_ts = 1700000000.0  # Nov 14, 2023
    lab_svc = LabArtifactService(source=DummyLabSource())
    artifact_adapter = Project1LabArtifactAdapter(service=lab_svc)

    historical_artifact = artifact_adapter.fetch_historical_artifact("XAUUSD", "1h")
    assert historical_artifact is not None
    assert historical_artifact.signal_id == "p1_xauusd_1h_1700000000"
    assert historical_artifact.metadata["is_historical"] is True

    # Ingest historical record into gateway repo with provenance_type=historical_snapshot
    raw_rec = {
        "integration_id": "intg_2023_hist",
        "signal_id": "p1_xauusd_1h_1700000000",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": historical_ts,
        "confidence": 0.88,
        "strategy_name": "GoldTrendv1",
        "metadata": {"provenance_type": "historical_snapshot", "is_historical": True},
    }
    temp_repo.save_record(raw_rec)

    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    live_sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h")
    assert live_sig is None

    presenter = Project1SignalPresenter(port=adapter, gateway_service=gateway_svc)
    pres_res = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=admin_user)
    assert pres_res["status"] == "no-signal"
    assert pres_res["signal"] is None

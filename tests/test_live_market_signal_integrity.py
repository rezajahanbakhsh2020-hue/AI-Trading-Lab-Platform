"""Regression and integration test suite verifying live market, live signal,
chart overlay preconditions, market quote price purity, and timeline consistency for Project 2.

Covers MISSION requirements A, B, C, D, G, H, I:
- Live signal authenticity and provenance safety
- Market quote price integrity (zero fallback to signal entry prices)
- Signal level preservation without Project 2 recalculation
- Timeline consistency for live signals
- Cross-layer consistency trace for XAUUSD
"""

import time
import pytest
from src.platform.adapters.project1_adapter import Project1GatewayAdapter, Project1LabArtifactAdapter
from src.platform.adapters.project1_repository import FileBackedProject1IntegrationRepository
from src.platform.domain.presented_signal import PresentedSignal
from src.platform.domain.security import Permission
from src.platform.domain.user_authorization import UserAuthorization, UserRole
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.clock import SystemClock
from src.platform.services.intelligence_timeline import IntelligenceTimelineService
from src.platform.services.lab_artifacts import LabArtifactService
from src.platform.services.project1_gateway import Project1IntegrationGatewayService
from src.platform.services.project1_presenter import Project1SignalPresenter, _evaluate_signal_live_status
from src.platform.services.security import SecurityBoundaryService


class MockClock(SystemClock):
    def __init__(self, fixed_time: float) -> None:
        self._fixed_time = fixed_time

    def get_current_timestamp(self) -> float:
        return self._fixed_time

    def get_current_date(self) -> str:
        return self.get_date_for_timestamp(self._fixed_time)


class DummyGatewayRepo:
    def __init__(self, records=None) -> None:
        self.records = records or []

    def list_records_for_user(self, user_id=None, symbol=None, lifecycle_state=None, limit=500):
        res = []
        for r in self.records:
            if symbol and r.get("symbol") and r.get("symbol").upper() != symbol.upper():
                continue
            res.append(r)
        return res[:limit]


class DummyGatewayService:
    def __init__(self, repo) -> None:
        self._repo = repo

    def get_gateway_monitoring_summary(self, user=None):
        return {"status": "ACTIVE", "total_records": len(self._repo.records)}


def test_live_signal_authenticity_eligibility():
    """Verify Section A: Live signal authenticity requirements."""
    now_ts = 1700000000.0
    clk = MockClock(now_ts)

    # 1. Valid live signal
    valid_sig = {
        "symbol": "XAUUSD",
        "timestamp": now_ts - 50.0,
        "metadata": {"provenance_type": "live_signal", "is_live": True},
    }
    is_live, reason = _evaluate_signal_live_status(valid_sig, requested_symbol="XAUUSD", clock=clk)
    assert is_live is True
    assert "Verified current live signal" in reason

    # 2. Reject lab artifact / historical
    lab_sig = {
        "symbol": "XAUUSD",
        "timestamp": now_ts - 50.0,
        "metadata": {"provenance_type": "lab_artifact", "is_historical": True},
    }
    is_live, reason = _evaluate_signal_live_status(lab_sig, requested_symbol="XAUUSD", clock=clk)
    assert is_live is False
    assert "historical artifact" in reason

    # 3. Reject stale timestamp (> 300s)
    stale_sig = {
        "symbol": "XAUUSD",
        "timestamp": now_ts - 350.0,
        "metadata": {"provenance_type": "live_signal"},
    }
    is_live, reason = _evaluate_signal_live_status(stale_sig, requested_symbol="XAUUSD", clock=clk)
    assert is_live is False
    assert "stale" in reason

    # 4. Reject future timestamp
    future_sig = {
        "symbol": "XAUUSD",
        "timestamp": now_ts + 100.0,
        "metadata": {"provenance_type": "live_signal"},
    }
    is_live, reason = _evaluate_signal_live_status(future_sig, requested_symbol="XAUUSD", clock=clk)
    assert is_live is False
    assert "future" in reason

    # 5. Reject symbol mismatch
    mismatch_sig = {
        "symbol": "EURUSD",
        "timestamp": now_ts - 10.0,
        "metadata": {"provenance_type": "live_signal"},
    }
    is_live, reason = _evaluate_signal_live_status(mismatch_sig, requested_symbol="XAUUSD", clock=clk)
    assert is_live is False
    assert "symbol" in reason.lower()


def test_event_time_ordering_over_insertion_order():
    """Verify Section A: Newer live signal selected over older inserted record."""
    now_ts = 1700000000.0
    repo = DummyGatewayRepo(
        records=[
            {
                "signal_id": "sig_newer_event",
                "symbol": "XAUUSD",
                "signal_type": "buy",
                "timestamp": now_ts - 10.0,  # Newer event time
                "entry_price": 2650.0,
                "created_at": now_ts - 5.0,
                "metadata": {"provenance_type": "live_signal"},
            },
            {
                "signal_id": "sig_older_event_inserted_later",
                "symbol": "XAUUSD",
                "signal_type": "sell",
                "timestamp": now_ts - 200.0,  # Older event time
                "entry_price": 2640.0,
                "created_at": now_ts - 1.0,  # Inserted later
                "metadata": {"provenance_type": "live_signal"},
            },
        ]
    )
    adapter = Project1GatewayAdapter(gateway_service=DummyGatewayService(repo))
    fetched = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h")

    assert fetched is not None
    assert fetched.signal_id == "sig_newer_event"
    assert fetched.timestamp == now_ts - 10.0
    assert fetched.entry_price == 2650.0


def test_market_price_purity_no_signal_entry_fallback():
    """Verify Section B: Presenter market snapshot never falls back to signal entry price."""
    now_ts = time.time()
    repo = DummyGatewayRepo(
        records=[
            {
                "signal_id": "p1_xauusd_live",
                "symbol": "XAUUSD",
                "signal_type": "buy",
                "timestamp": now_ts - 20.0,
                "entry_price": 2650.50,
                "stop_loss": 2635.00,
                "take_profit_1": 2670.00,
                "metadata": {"provenance_type": "live_signal"},
            }
        ]
    )
    gw_service = DummyGatewayService(repo)
    adapter = Project1GatewayAdapter(gateway_service=gw_service)
    presenter = Project1SignalPresenter(port=adapter, gateway_service=gw_service)

    # Request host snapshot without market quote provider attached
    snapshot = presenter.build_host_snapshot(symbol="XAUUSD", timeframe="1h")

    # Market quote MUST be None or empty, NOT fallen back to signal entry price 2650.50
    assert snapshot["market"]["quote"] is None
    assert snapshot["risk"]["entry"] == 2650.50  # Risk level preserved separately
    assert snapshot["signal"]["action"] == "BUY"


def test_timeline_consistency_live_signal_only():
    """Verify Section H: Timeline service includes signal event ONLY when signal is active and live."""
    now_ts = time.time()
    timeline_service = IntelligenceTimelineService()
    user = UserAuthorization(
        user_id="usr_01",
        auth_code="code01",
        role=UserRole.USER,
        permissions=[Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS],
    )

    # Active live signal snapshot
    active_snapshot = {
        "project1": {"connected": True, "adapterName": "Project1GatewayAdapter"},
        "market": {"symbol": "XAUUSD", "status": "connected"},
        "signal": {
            "signalId": "p1_xauusd_100",
            "symbol": "XAUUSD",
            "action": "BUY",
            "timestamp": str(now_ts - 30.0),
            "status": "active",
            "strategyName": "GoldTrend",
            "metadata": {"provenance_type": "live_signal"},
        },
    }
    items = timeline_service.build_timeline(user=user, snapshot=active_snapshot)
    sig_items = [i for i in items if i.category.value == "signal"]
    assert len(sig_items) == 1
    assert sig_items[0].title == "BUY Signal for XAUUSD"

    # Inactive / NO SIGNAL snapshot
    no_sig_snapshot = {
        "project1": {"connected": True, "adapterName": "Project1GatewayAdapter"},
        "market": {"symbol": "XAUUSD", "status": "connected"},
        "signal": {
            "signalId": None,
            "symbol": "XAUUSD",
            "action": "NO SIGNAL",
            "timestamp": None,
            "status": "no-signal",
            "metadata": {},
        },
    }
    items_no_sig = timeline_service.build_timeline(user=user, snapshot=no_sig_snapshot)
    sig_items_no_sig = [i for i in items_no_sig if i.category.value == "signal"]
    assert len(sig_items_no_sig) == 0


def test_cross_layer_xauusd_consistency_trace(tmp_path):
    """Verify Section I: Complete cross-layer trace for XAUUSD from Gateway -> Presenter -> Snapshot -> Timeline."""
    now_ts = time.time()
    sec_boundary = SecurityBoundaryService()
    audit_control = PlatformAuditControlService(security_boundary=sec_boundary)

    # 1. Gateway Repo & Gateway Service
    store_file = tmp_path / "project1_records.json"
    repo = FileBackedProject1IntegrationRepository(storage_filepath=str(store_file), audit_control=audit_control)

    user = UserAuthorization(
        user_id="owner_1",
        auth_code="owner_code",
        role=UserRole.OWNER,
        permissions=[Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS],
    )

    # Ingest Contract v1.0 payload
    ingest_record = {
        "integration_id": "ingest_001",
        "command_type": "EMIT_SIGNAL",
        "signal_id": "sig_xauusd_cross_layer_001",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "strategy_name": "GoldTrendv1",
        "signal_type": "BUY",
        "timestamp": now_ts - 25.0,
        "entry_price": 2650.00,
        "stop_loss": 2635.00,
        "take_profit_1": 2670.00,
        "take_profit_2": 2690.00,
        "take_profit_3": 2710.00,
        "confidence": 0.88,
        "metadata": {"provenance_type": "live_signal", "is_live": True},
    }
    repo.save_record(record=ingest_record)

    gw_service = Project1IntegrationGatewayService(
        repository=repo, security_boundary=sec_boundary, audit_control=audit_control
    )

    # 2. Project1GatewayAdapter
    adapter = Project1GatewayAdapter(gateway_service=gw_service)
    latest_sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h")

    assert latest_sig is not None
    assert latest_sig.signal_id == "sig_xauusd_cross_layer_001"
    assert latest_sig.symbol == "XAUUSD"
    assert latest_sig.entry_price == 2650.00
    assert latest_sig.stop_loss == 2635.00
    assert latest_sig.take_profits == (2670.00, 2690.00, 2710.00)

    # 3. Presenter -> Host Snapshot
    presenter = Project1SignalPresenter(
        port=adapter,
        security_service=sec_boundary,
        audit_control_service=audit_control,
        gateway_service=gw_service,
    )
    snapshot = presenter.build_host_snapshot(symbol="XAUUSD", timeframe="1h", user=user)

    assert snapshot["project1"]["connected"] is True
    assert snapshot["signal"]["signalId"] == "sig_xauusd_cross_layer_001"
    assert snapshot["signal"]["symbol"] == "XAUUSD"
    assert snapshot["signal"]["action"] == "BUY"
    assert snapshot["signal"]["status"] == "active"
    assert snapshot["risk"]["entry"] == 2650.00
    assert snapshot["risk"]["stopLoss"] == 2635.00
    assert snapshot["risk"]["takeProfits"] == [2670.00, 2690.00, 2710.00]

    # 4. Intelligence Timeline Trace
    timeline_service = IntelligenceTimelineService(security_boundary=sec_boundary)
    items = timeline_service.build_timeline(user=user, snapshot=snapshot)
    sig_items = [i for i in items if i.category.value == "signal"]

    assert len(sig_items) == 1
    assert sig_items[0].payload["signal_id"] == "sig_xauusd_cross_layer_001"
    assert sig_items[0].payload["symbol"] == "XAUUSD"
    assert sig_items[0].payload["action"] == "BUY"

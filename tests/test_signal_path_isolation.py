"""Comprehensive Regression Test Suite for Architectural Data-Path Isolation & Current Signal Boundary.

Verifies:
1. Historical/archive records (e.g. 2023 'p1_xauusd_1h_1700000000', 2020, 2010, 2000) are REJECTED
   by the Current Signal API while remaining ALLOWED for Backtest / Laboratory analysis.
2. Hard 5-minute (300s) freshness boundary (299s ACCEPTED, 301s REJECTED).
3. Previous calendar date rejection.
4. Outbound delivery protection (Telegram delivery blocks stale/historical records).
5. Future / invalid timestamp rejection.
"""

from datetime import datetime, timezone
import time
import pytest

from src.platform.adapters.project1_adapter import DisconnectedProject1Adapter, Project1GatewayAdapter, Project1LabArtifactAdapter
from src.platform.adapters.project1_repository import FileBackedProject1IntegrationRepository
from src.platform.domain.presented_signal import PresentedSignal
from src.platform.domain.user_authorization import UserAuthorization, UserRole
from src.platform.integrations.lab import LabArtifactSource
from src.platform.integrations.telegram import TelegramDeliveryPort, TelegramDeliveryResult
from src.platform.services.clock import SystemClock
from src.platform.services.lab_artifacts import LabArtifactService
from src.platform.services.project1_gateway import Project1IntegrationGatewayService
from src.platform.services.project1_presenter import Project1SignalPresenter, _evaluate_signal_live_status
from src.platform.services.telegram_delivery import TelegramDeliveryService
from src.platform.services.user_authorization import UserAuthorizationService


class MockLabSource(LabArtifactSource):
    def __init__(self, signal_data=None, setup_data=None):
        self._signal_data = signal_data
        self._setup_data = setup_data

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def fetch_signal(self, symbol: str, timeframe: str):
        return self._signal_data

    def fetch_trade_setup(self, symbol: str, timeframe: str):
        return self._setup_data

    def fetch_stability(self, strategy_name: str):
        return {"score": 0.85, "risk_level": "low", "metrics": {"win_rate": 0.65}}

    def fetch_walk_forward(self, strategy_name: str):
        return None

    def describe(self):
        return {"name": "MockLabSource", "status": "active"}


class MockTelegramPort(TelegramDeliveryPort):
    def __init__(self):
        self.sent_signals = []

    def send_signal(self, chat_id: str, signal: PresentedSignal) -> TelegramDeliveryResult:
        self.sent_signals.append((chat_id, signal))
        return TelegramDeliveryResult(
            success=True,
            chat_id=chat_id,
            message_id="msg_123",
            delivered_at=time.time(),
            reason="Delivered successfully",
        )

    def describe(self):
        return {"name": "MockTelegramPort", "status": "active"}


@pytest.fixture
def mock_admin_user():
    return UserAuthorization(
        user_id="usr_admin",
        auth_code="code_admin",
        role=UserRole.ADMIN,
    )


def test_incident_regression_2023_archive_rejected_by_current_signal_allowed_by_backtest(tmp_path, mock_admin_user):
    """Prove p1_xauusd_1h_1700000000 (Nov 2023) is REJECTED by Current Signal API and ALLOWED by Backtest API."""
    # 1. Backtest / Lab domain retains historical artifact
    historical_ts = 1700000000.0  # Nov 14, 2023
    lab_source = MockLabSource(
        signal_data={"action": "BUY", "strategy_name": "GoldTrendv1", "timestamp": historical_ts, "confidence": 0.88},
        setup_data={
            "symbol": "XAUUSD",
            "entry_price": 1980.0,
            "stop_loss": 1960.0,
            "take_profit_1": 2000.0,
            "take_profit_2": 2020.0,
            "take_profit_3": 2040.0,
            "timestamp": historical_ts,
            "direction": "BUY",
        },
    )
    lab_svc = LabArtifactService(lab_source)
    artifact_adapter = Project1LabArtifactAdapter(lab_svc)

    # Historical record is validly accessible in Laboratory / Backtest domain
    historical_artifact = artifact_adapter.fetch_historical_artifact("XAUUSD", "1h")
    assert historical_artifact is not None
    assert historical_artifact.signal_id == "p1_xauusd_1h_1700000000"
    assert historical_artifact.metadata["is_historical"] is True

    # 2. Current Signal Feed uses Project1GatewayAdapter (live port)
    repo = FileBackedProject1IntegrationRepository(storage_filepath=str(tmp_path / "gw_repo.json"))
    gw_svc = Project1IntegrationGatewayService(repository=repo)
    live_port = Project1GatewayAdapter(gateway_service=gw_svc)
    presenter = Project1SignalPresenter(port=live_port, gateway_service=gw_svc)

    # Ingest historical record into repository
    gw_svc.ingest_signal_payload(
        user=mock_admin_user,
        payload={
            "integration_id": "intg_2023_hist",
            "signal_id": "p1_xauusd_1h_1700000000",
            "symbol": "XAUUSD",
            "timeframe": "1h",
            "signal_type": "buy",
            "timestamp": historical_ts,
            "confidence": 0.88,
            "strategy_name": "GoldTrendv1",
            "entry_price": 1980.0,
            "stop_loss": 1960.0,
            "take_profit_1": 2000.0,
            "metadata": {"provenance_type": "historical_snapshot", "is_historical": True},
        },
    )

    # Query Current Signal API
    current_signal_response = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=mock_admin_user)
    assert current_signal_response["status"] == "no-signal"
    assert current_signal_response["signal"] is None
    assert "No active" in current_signal_response["message"]


def test_multi_year_archive_rejection_from_current_signal(tmp_path, mock_admin_user):
    """Test 2023, 2020, 2010, 2000 archive dates are ALL rejected by Current Signal API."""
    repo = FileBackedProject1IntegrationRepository(storage_filepath=str(tmp_path / "gw_repo_multi.json"))
    gw_svc = Project1IntegrationGatewayService(repository=repo)
    live_port = Project1GatewayAdapter(gateway_service=gw_svc)
    presenter = Project1SignalPresenter(port=live_port, gateway_service=gw_svc)

    years = [2023, 2020, 2010, 2000]
    for yr in years:
        dt = datetime(yr, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        ts = dt.timestamp()
        sig_id = f"sig_{yr}_test"

        gw_svc.ingest_signal_payload(
            user=mock_admin_user,
            payload={
                "integration_id": f"intg_{yr}",
                "signal_id": sig_id,
                "symbol": "XAUUSD",
                "timeframe": "1h",
                "signal_type": "buy",
                "timestamp": ts,
                "confidence": 0.80,
                "strategy_name": "TestStrat",
                "metadata": {"provenance_type": "live_signal"},
            },
        )

        res = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=mock_admin_user)
        assert res["status"] == "no-signal"
        assert res["signal"] is None


def test_hard_5_minute_freshness_boundary(tmp_path, mock_admin_user):
    """Test synthetic live signal: age 299s (ACCEPTED) vs age 301s (REJECTED)."""
    now = time.time()
    clk = SystemClock(fixed_timestamp=now)

    # Signal 1: 299 seconds ago (FRESH)
    sig_fresh_ts = now - 299.0
    sig_fresh_dict = {
        "signal_id": "sig_fresh",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": sig_fresh_ts,
        "metadata": {"provenance_type": "live_signal"},
    }
    is_live_fresh, _ = _evaluate_signal_live_status(sig_fresh_dict, clock=clk)
    assert is_live_fresh is True

    # Signal 2: 301 seconds ago (STALE)
    sig_stale_ts = now - 301.0
    sig_stale_dict = {
        "signal_id": "sig_stale",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": sig_stale_ts,
        "metadata": {"provenance_type": "live_signal"},
    }
    is_live_stale, reason_stale = _evaluate_signal_live_status(sig_stale_dict, clock=clk)
    assert is_live_stale is False
    assert "stale" in reason_stale


def test_previous_date_rejection(tmp_path):
    """Test signal from previous UTC calendar date is rejected even if age <= 300s across midnight."""
    # System time: 2026-03-31 00:01:00 UTC (timestamp 1774915260)
    system_dt = datetime(2026, 3, 31, 0, 1, 0, tzinfo=timezone.utc)
    now_ts = system_dt.timestamp()
    clk = SystemClock(fixed_timestamp=now_ts)

    # Signal time: 2026-03-30 23:59:30 UTC (timestamp 1774915170) -> 90 seconds ago, but PREVIOUS DATE
    sig_dt = datetime(2026, 3, 30, 23, 59, 30, tzinfo=timezone.utc)
    sig_ts = sig_dt.timestamp()

    sig_dict = {
        "signal_id": "sig_prev_date",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": sig_ts,
        "metadata": {"provenance_type": "live_signal"},
    }

    is_live, reason = _evaluate_signal_live_status(sig_dict, clock=clk)
    assert is_live is False
    assert "does not match current application date" in reason


def test_future_and_invalid_timestamp_rejection():
    """Test missing, negative, or future timestamps are rejected."""
    clk = SystemClock(fixed_timestamp=1700000000.0)

    # Future timestamp (+100s)
    future_sig = {
        "signal_id": "sig_fut",
        "symbol": "XAUUSD",
        "timestamp": 1700000100.0,
        "metadata": {"provenance_type": "live_signal"},
    }
    is_live_fut, reason_fut = _evaluate_signal_live_status(future_sig, clock=clk)
    assert is_live_fut is False
    assert "future" in reason_fut

    # Missing timestamp
    missing_sig = {
        "signal_id": "sig_miss",
        "symbol": "XAUUSD",
        "metadata": {"provenance_type": "live_signal"},
    }
    is_live_miss, _ = _evaluate_signal_live_status(missing_sig, clock=clk)
    assert is_live_miss is False


def test_outbound_telegram_delivery_blocks_stale_and_historical_signals():
    """Prove Telegram delivery gate rejects stale or historical signals."""
    tg_port = MockTelegramPort()
    auth_svc = UserAuthorizationService()

    user = UserAuthorization(
        user_id="usr_tg",
        auth_code="code_tg",
        telegram_chat_id="12345678",
        delivery_enabled=True,
        role=UserRole.USER,
    )
    auth_svc.register_user(user)

    delivery_svc = TelegramDeliveryService(delivery_port=tg_port, user_auth_service=auth_svc)

    # Stale signal from 2023
    stale_signal = PresentedSignal(
        signal_id="p1_xauusd_1h_1700000000",
        symbol="XAUUSD",
        signal_type="buy",
        timestamp=1700000000.0,
        metadata={"provenance_type": "historical_snapshot"},
    )

    res = delivery_svc.deliver_signal_to_user(user_id="usr_tg", signal=stale_signal)
    assert res.success is False
    assert "Delivery blocked: Signal failed Current Signal eligibility check" in res.reason
    assert len(tg_port.sent_signals) == 0


def test_evaluate_signal_live_status_symbol_mismatch_rejection():
    """Verify signal is rejected when signal symbol does not match requested market symbol."""
    clk = SystemClock(fixed_timestamp=1700000000.0)

    sig = {
        "signal_id": "p1_eurusd_1h_live",
        "symbol": "EURUSD",
        "timestamp": 1700000000.0,
        "metadata": {"provenance_type": "live_signal"},
    }

    # Requesting XAUUSD for an EURUSD signal
    is_live, reason = _evaluate_signal_live_status(sig, requested_symbol="XAUUSD", clock=clk)
    assert is_live is False
    assert "Signal symbol 'EURUSD' does not match requested market symbol 'XAUUSD'" in reason


def test_presenter_adapter_name_default_is_gateway_adapter():
    """Verify Project1SignalPresenter defaults adapterName to Project1GatewayAdapter when connected."""
    class DummyRepoPort:
        def list_records_for_user(self, user_id=None, symbol=None, lifecycle_state=None, limit=500):
            if limit == 1:
                return [{"signal_id": "dummy"}]
            return []

    class DummyGatewayService:
        def __init__(self):
            self._repo = DummyRepoPort()
        def get_gateway_monitoring_summary(self, user=None):
            return {}

    gw = DummyGatewayService()
    adapter = Project1GatewayAdapter(gateway_service=gw)
    presenter = Project1SignalPresenter(port=adapter, gateway_service=gw)

    snapshot = presenter.build_host_snapshot(symbol="XAUUSD")
    assert snapshot["project1"]["connected"] is True
    assert snapshot["project1"]["adapterName"] == "Project1GatewayAdapter"
    assert snapshot["project1"]["adapterName"] != "Project1LabArtifactAdapter"
    assert snapshot["signal"]["status"] == "no-signal"
    assert snapshot["signal"]["action"] == "NO SIGNAL"

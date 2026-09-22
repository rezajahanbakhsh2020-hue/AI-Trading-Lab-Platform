import os
import sys
import time
import pytest

sys.path.insert(0, ".")

from src.platform.adapters.project1_adapter import Project1GatewayAdapter, Project1LabArtifactAdapter
from src.platform.integrations.project1 import Project1IntegrationPort
from src.platform.adapters.project1_repository import FileBackedProject1IntegrationRepository
from src.platform.domain.security import UserRole, Permission
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.lab_artifacts import LabArtifactService
from src.platform.integrations.lab import LabArtifactSource
from src.platform.services.project1_gateway import Project1IntegrationGatewayService
from src.platform.services.project1_presenter import Project1SignalPresenter

@pytest.fixture
def temp_repo(tmp_path):
    storage_file = str(tmp_path / "p1_records_test.json")
    return FileBackedProject1IntegrationRepository(storage_filepath=storage_file)

@pytest.fixture
def gateway_svc(temp_repo):
    return Project1IntegrationGatewayService(repository=temp_repo)

@pytest.fixture
def admin_user():
    return UserAuthorization(
        user_id="admin_test",
        auth_code="code_test_123",
        role=UserRole.ADMIN,
        is_permanent_admin=True,
    )

def test_gateway_adapter_init_validation():
    with pytest.raises(ValueError, match="gateway_service must be provided"):
        Project1GatewayAdapter(gateway_service=None)

def test_gateway_adapter_empty_repo_returns_none(gateway_svc):
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)

    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h")
    assert sig is None

    desc = adapter.describe()
    assert desc["name"] == "Project1GatewayAdapter"
    assert desc["port"] == "Project1IntegrationPort"
    assert desc["connected"] is True
    assert desc["status"] == "ready"

def test_gateway_adapter_fetches_ingested_signal(gateway_svc, admin_user):
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)

    payload = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "integ_test_001",
        "signal_id": "p1_xauusd_1h_live_001",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": time.time() - 20,
        "entry_price": 2765.50,
        "stop_loss": 2750.00,
        "take_profit_1": 2785.00,
        "take_profit_2": 2800.00,
        "confidence": 0.92,
        "strategy_name": "LiveGoldStrategy",
        "metadata": {"provenance_type": "live_signal"},
    }

    ingest_res = gateway_svc.ingest_signal_payload(user=admin_user, payload=payload)
    assert ingest_res["success"] is True

    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h")
    assert sig is not None
    assert sig.symbol == "XAUUSD"
    assert sig.signal_type == "buy"
    assert sig.entry_price == 2765.50
    assert sig.stop_loss == 2750.00
    assert sig.take_profits == (2785.00, 2800.00)
    assert sig.confidence == 0.92
    assert sig.strategy_name == "LiveGoldStrategy"
    assert sig.timeframe == "1h"
    assert sig.metadata.get("provenance_type") == "live_signal"
    assert sig.metadata.get("adapter") == "Project1GatewayAdapter"

    desc = adapter.describe()
    assert desc["connected"] is True
    assert desc["status"] == "active"

def test_gateway_adapter_presenter_scenarios(gateway_svc, admin_user):
    adapter = Project1GatewayAdapter(gateway_service=gateway_svc)
    presenter = Project1SignalPresenter(port=adapter, gateway_service=gateway_svc)

    # 1. Empty Repo -> Gateway Connected / Signal Unavailable (no-signal)
    pres_empty = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=admin_user)
    assert pres_empty["connected"] is True
    assert pres_empty["status"] == "no-signal"

    # 2. Fresh Live Signal Ingestion (<= 300s) -> Active
    fresh_ts = time.time() - 30
    payload_fresh = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "integ_test_fresh",
        "signal_id": "p1_xauusd_1h_live_fresh",
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "signal_type": "buy",
        "timestamp": fresh_ts,
        "entry_price": 2765.50,
        "stop_loss": 2750.00,
        "take_profit_1": 2785.00,
        "confidence": 0.92,
        "strategy_name": "LiveGoldStrategy",
        "metadata": {"provenance_type": "live_signal"},
    }
    gateway_svc.ingest_signal_payload(user=admin_user, payload=payload_fresh)

    pres_live = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=admin_user)
    assert pres_live["connected"] is True
    assert pres_live["status"] == "active"
    assert pres_live["signal"]["entry_price"] == 2765.50
    assert pres_live["signal"]["is_live"] is True

    # 3. Stale Gateway Record (> 300s) -> Rejected from Current Signal Feed
    stale_ts = time.time() - 600
    payload_stale = {
        "contract_version": "1.0",
        "command_type": "EMIT_SIGNAL",
        "integration_id": "integ_test_stale",
        "signal_id": "p1_xauusd_1h_stale",
        "symbol": "EURUSD",
        "timeframe": "1h",
        "signal_type": "sell",
        "timestamp": stale_ts,
        "entry_price": 1.0850,
        "stop_loss": 1.0900,
        "take_profit_1": 1.0800,
        "confidence": 0.88,
        "strategy_name": "EuroTrend",
        "metadata": {"provenance_type": "live_signal"},
    }
    gateway_svc.ingest_signal_payload(user=admin_user, payload=payload_stale)

    pres_stale = presenter.present_signal(symbol="EURUSD", timeframe="1h", user=admin_user)
    assert pres_stale["connected"] is True
    assert pres_stale["status"] == "no-signal"
    assert pres_stale["signal"] is None

def test_historical_lab_artifact_blocked_from_live(gateway_svc, admin_user):
    class DummyLabSource(LabArtifactSource):
        def connect(self):
            return True
        def close(self):
            pass
        def describe(self):
            return {"name": "DummyLab"}
        def fetch_signal(self, symbol, timeframe):
            return {"action": "BUY", "strategy_name": "GoldTrendv1", "timestamp": 1700000000.0, "confidence": 0.88}
        def fetch_trade_setup(self, symbol, timeframe):
            return {"symbol": symbol, "entry_price": 2650.50, "stop_loss": 2635.0, "take_profit_1": 2670.0, "take_profit_2": 2690.0, "take_profit_3": 2710.0, "timestamp": 1700000000.0, "direction": "buy"}
        def fetch_stability(self, strategy_name):
            return None
        def fetch_walk_forward(self, strategy_name):
            return None

    lab_adapter = Project1LabArtifactAdapter(service=LabArtifactService(source=DummyLabSource()))
    assert not isinstance(lab_adapter, Project1IntegrationPort)

    historical_artifact = lab_adapter.fetch_historical_artifact("XAUUSD", "1h")
    assert historical_artifact is not None
    assert historical_artifact.metadata["provenance_type"] == "lab_artifact"
    assert historical_artifact.metadata["is_historical"] is True

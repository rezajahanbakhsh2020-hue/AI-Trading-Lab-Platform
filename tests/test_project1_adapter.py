"""Focused tests for Project1LabArtifactAdapter and DisconnectedProject1Adapter."""

from typing import Any, Dict, Optional
import pytest

from src.platform.adapters.project1_adapter import (
    DisconnectedProject1Adapter,
    Project1LabArtifactAdapter,
)
from src.platform.domain.presented_signal import PresentedSignal
from src.platform.integrations.lab import LabArtifactSource
from src.platform.services.lab_artifacts import LabArtifactService


class MockLabArtifactSource(LabArtifactSource):
    """Mock source for testing Project 1 integration adapter."""

    def __init__(
        self,
        signal_data: Optional[Dict[str, Any]] = None,
        setup_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._signal_data = signal_data
        self._setup_data = setup_data

    def connect(self) -> None:
        pass

    def fetch_signal(self, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        return self._signal_data

    def fetch_trade_setup(self, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        return self._setup_data

    def fetch_stability(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        return None

    def close(self) -> None:
        pass

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "MockLabArtifactSource",
            "connected": True,
        }


def test_disconnected_adapter_returns_none_and_describes_status():
    adapter = DisconnectedProject1Adapter()
    sig = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h")
    assert sig is None

    desc = adapter.describe()
    assert desc["name"] == "DisconnectedProject1Adapter"
    assert desc["port"] == "Project1IntegrationPort"
    assert desc["connected"] is False
    assert desc["status"] == "disconnected"


def test_lab_artifact_adapter_maps_real_signal_and_setup_to_presented_signal():
    signal_raw = {
        "action": "BUY",
        "strategy_name": "MomentumGold",
        "timestamp": 1700000000.0,
        "confidence": 0.92,
    }
    setup_raw = {
        "symbol": "XAUUSD",
        "entry_price": 2050.5,
        "stop_loss": 2040.0,
        "take_profit_1": 2070.0,
        "take_profit_2": 2085.0,
        "take_profit_3": 2100.0,
        "timestamp": 1700000000.0,
        "direction": "buy",
    }
    source = MockLabArtifactSource(signal_data=signal_raw, setup_data=setup_raw)
    service = LabArtifactService(source=source)
    adapter = Project1LabArtifactAdapter(service=service)

    presented = adapter.fetch_historical_artifact(symbol="XAUUSD", timeframe="1h")

    assert isinstance(presented, PresentedSignal)
    assert presented.symbol == "XAUUSD"
    assert presented.signal_type == "buy"
    assert presented.strategy_name == "MomentumGold"
    assert presented.confidence == 0.92
    assert presented.entry_price == 2050.5
    assert presented.stop_loss == 2040.0
    assert presented.take_profits == (2070.0, 2085.0, 2100.0)
    assert presented.metadata["source"] == "Project1"


def test_lab_artifact_adapter_filters_by_strategy_name():
    signal_raw = {
        "action": "SELL",
        "strategy_name": "TrendFollower",
        "timestamp": 1700000000.0,
    }
    source = MockLabArtifactSource(signal_data=signal_raw)
    service = LabArtifactService(source=source)
    adapter = Project1LabArtifactAdapter(service=service)

    assert adapter.fetch_historical_artifact("EURUSD", "4h", strategy_name="OtherStrategy") is None
    matched = adapter.fetch_historical_artifact("EURUSD", "4h", strategy_name="TrendFollower")
    assert matched is not None
    assert matched.signal_type == "sell"


def test_lab_artifact_adapter_handles_missing_trade_setup():
    signal_raw = {
        "action": "BUY",
        "strategy_name": "SimpleRSI",
        "timestamp": 1700000000.0,
    }
    source = MockLabArtifactSource(signal_data=signal_raw, setup_data=None)
    service = LabArtifactService(source=source)
    adapter = Project1LabArtifactAdapter(service=service)

    presented = adapter.fetch_historical_artifact(symbol="BTCUSD", timeframe="15m")
    assert presented is not None
    assert presented.entry_price is None
    assert presented.stop_loss is None
    assert presented.take_profits == ()


def test_lab_artifact_adapter_describe():
    source = MockLabArtifactSource()
    service = LabArtifactService(source=source)
    adapter = Project1LabArtifactAdapter(service=service)
    desc = adapter.describe()

    assert desc["name"] == "Project1LabArtifactAdapter"
    assert desc["port"] == "HistoricalLabArtifactPort"
    assert desc["connected"] is True
    assert desc["source"]["name"] == "MockLabArtifactSource"

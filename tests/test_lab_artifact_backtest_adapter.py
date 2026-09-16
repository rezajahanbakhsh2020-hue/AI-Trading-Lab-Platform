from unittest.mock import MagicMock
import pytest

from src.platform.adapters.project1_adapter import LabArtifactBacktestAdapter
from src.platform.domain.stability import Stability
from src.platform.integrations.lab import LabArtifactSource
from src.platform.services.lab_artifacts import LabArtifactService


def test_lab_artifact_backtest_adapter_initialization():
    with pytest.raises(ValueError, match="service must be a valid LabArtifactService"):
        LabArtifactBacktestAdapter(None)


def test_lab_artifact_backtest_adapter_run_backtest_success():
    mock_service = MagicMock(spec=LabArtifactService)
    mock_service.get_stability.return_value = Stability(
        score=0.85,
        risk_level="low",
        metrics={
            "total_trades": 100,
            "win_rate": 0.65,
            "profit_factor": 2.0,
            "max_drawdown": 0.10,
            "net_profit": 5000.0,
        },
    )

    adapter = LabArtifactBacktestAdapter(mock_service)
    res = adapter.run_backtest(
        strategy_name="TrendMaster",
        symbol="XAUUSD",
        timeframe="1h",
        candles=[],
    )

    assert res is not None
    assert res["strategy_name"] == "TrendMaster"
    assert res["symbol"] == "XAUUSD"
    assert res["timeframe"] == "1h"
    assert res["total_trades"] == 100
    assert res["win_rate"] == 0.65
    assert res["profit_factor"] == 2.0
    assert res["max_drawdown"] == 0.10
    assert res["net_profit"] == 5000.0


def test_lab_artifact_backtest_adapter_run_backtest_unavailable():
    mock_service = MagicMock(spec=LabArtifactService)
    mock_service.get_stability.return_value = None

    adapter = LabArtifactBacktestAdapter(mock_service)
    res = adapter.run_backtest(
        strategy_name="UnknownStrategy",
        symbol="XAUUSD",
        timeframe="1h",
        candles=[],
    )

    assert res is None


def test_lab_artifact_backtest_adapter_describe():
    mock_source = MagicMock(spec=LabArtifactSource)
    mock_source.describe.return_value = {"type": "mock_source"}
    service = LabArtifactService(source=mock_source)

    adapter = LabArtifactBacktestAdapter(service)
    desc = adapter.describe()

    assert desc["name"] == "LabArtifactBacktestAdapter"
    assert desc["port"] == "BacktestSource"
    assert desc["connected"] is True
    assert desc["source"] == {"type": "mock_source"}

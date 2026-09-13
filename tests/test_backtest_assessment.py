"""Focused tests for Part 17 BacktestAssessmentService and BacktestResult."""

from typing import Any, Dict, Optional, Sequence
import pytest

from src.platform.domain.backtest import BacktestResult
from src.platform.domain.market import Candle
from src.platform.integrations.backtest import BacktestSource
from src.platform.providers.market_data import MarketDataProvider
from src.platform.services.backtest_assessment import BacktestAssessmentService
from src.platform.services.provider_access import ProviderAccess
from src.platform.services.provider_operations import ProviderOperations
from src.platform.services.provider_registry import CATEGORY_MARKET_DATA, ProviderRegistry


class DummyMarketDataProvider(MarketDataProvider):
    def __init__(self, provider_id: str = "dummy_md", candles: Optional[list] = None):
        self._id = provider_id
        self._candles = candles if candles is not None else [
            Candle(
                timestamp=1000.0,
                open=100.0,
                high=105.0,
                low=99.0,
                close=102.0,
                volume=500.0,
            )
        ]

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def describe(self) -> Dict[str, Any]:
        return {
            "name": f"Dummy MD {self._id}",
            "status": "healthy",
            "supports_fetch_candles": True,
            "supported_symbols": ["XAUUSD"],
            "supported_timeframes": ["1h"],
        }

    def fetch_candles(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> list:
        return [
            {
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in self._candles
        ]


class DummyBacktestSource(BacktestSource):
    def __init__(self, raw_result: Optional[Dict[str, Any]] = None, use_default: bool = True):
        self.use_default = use_default
        self.raw_result = raw_result

    def run_backtest(
        self,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        candles: Sequence[Candle],
        initial_capital: float = 10000.0,
    ) -> Optional[Dict[str, Any]]:
        if not self.use_default:
            return self.raw_result
        if self.raw_result is not None:
            return self.raw_result
        return {
            "total_trades": 20,
            "win_rate": 0.65,
            "profit_factor": 1.8,
            "max_drawdown": 0.08,
            "net_profit": 1500.0,
        }

    def describe(self) -> Dict[str, Any]:
        return {"name": "Dummy Backtest Source"}


def _build_services(md_provider: Optional[MarketDataProvider] = None):
    registry = ProviderRegistry()
    md = md_provider or DummyMarketDataProvider("md1")
    registry.register("md1", CATEGORY_MARKET_DATA, md)
    access = ProviderAccess(registry)
    ops = ProviderOperations(access)
    return ops


def test_backtest_assessment_success():
    ops = _build_services()
    source = DummyBacktestSource()
    svc = BacktestAssessmentService(operations=ops, backtest_source=source)

    res = svc.run_assessment(
        strategy_name="Momentum",
        symbol="XAUUSD",
        timeframe="1h",
        market_data_provider_id="md1",
    )

    assert isinstance(res, BacktestResult)
    assert res.strategy_name == "Momentum"
    assert res.symbol == "XAUUSD"
    assert res.total_trades == 20
    assert res.win_rate == 0.65
    assert res.profit_factor == 1.8
    assert res.max_drawdown == 0.08
    assert res.net_profit == 1500.0
    assert res.stability is not None
    assert res.stability.risk_level == "low"
    assert res.stability.score > 0.7


def test_backtest_assessment_empty_candles():
    ops = _build_services(DummyMarketDataProvider("md1", candles=[]))
    source = DummyBacktestSource()
    svc = BacktestAssessmentService(operations=ops, backtest_source=source)

    res = svc.run_assessment(
        strategy_name="Momentum",
        symbol="XAUUSD",
        timeframe="1h",
        market_data_provider_id="md1",
    )

    assert res.total_trades == 0
    assert res.win_rate == 0.0
    assert res.stability is not None
    assert res.stability.risk_level == "critical"
    assert "no candles available" in res.detail


def test_backtest_assessment_unavailable_source():
    ops = _build_services()
    source = DummyBacktestSource(raw_result=None, use_default=False)
    svc = BacktestAssessmentService(operations=ops, backtest_source=source)

    res = svc.run_assessment(
        strategy_name="Momentum",
        symbol="XAUUSD",
        timeframe="1h",
        market_data_provider_id="md1",
    )

    assert res.total_trades == 0
    assert res.stability.risk_level == "critical"
    assert "unavailable" in res.detail


def test_backtest_assessment_input_validation():
    ops = _build_services()
    source = DummyBacktestSource()
    svc = BacktestAssessmentService(operations=ops, backtest_source=source)

    with pytest.raises(ValueError):
        svc.run_assessment("", "XAUUSD", "1h", "md1")

    with pytest.raises(ValueError):
        svc.run_assessment("Momentum", "", "1h", "md1")

    with pytest.raises(ValueError):
        svc.run_assessment("Momentum", "XAUUSD", "1h", "md1", initial_capital=-100)


def test_backtest_result_to_dict():
    res = BacktestResult(
        strategy_name="Momentum",
        symbol="XAUUSD",
        timeframe="1h",
        total_trades=10,
        win_rate=0.6,
        profit_factor=1.5,
        max_drawdown=0.1,
        net_profit=500.0,
    )
    d = res.to_dict()
    assert d["strategy_name"] == "Momentum"
    assert d["symbol"] == "XAUUSD"
    assert d["total_trades"] == 10
    assert d["win_rate"] == 0.6

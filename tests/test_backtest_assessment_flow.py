"""Comprehensive unit tests for Backtest Assessment Flow end-to-end integration."""

import pytest

from src.platform.adapters.project1_adapter import Project1LabArtifactAdapter
from src.platform.domain.market import Candle
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.integrations.backtest import BacktestSource
from src.platform.integrations.lab import LabArtifactSource
from src.platform.providers.biquote_quote import BiQuoteQuoteProvider
from src.platform.providers.market_data import MarketDataProvider
from src.platform.services.backtest_assessment import BacktestAssessmentService
from src.platform.services.lab_artifacts import LabArtifactService
from src.platform.services.project1_presenter import Project1SignalPresenter
from src.platform.services.provider_access import ProviderAccess
from src.platform.services.provider_operations import ProviderOperations
from src.platform.services.provider_registry import (
    CATEGORY_MARKET_DATA,
    CATEGORY_QUOTE,
    ProviderRegistry,
)
from src.platform.services.security import SecurityBoundaryService


class MockBacktestSource(BacktestSource):
    """Mock BacktestSource for testing backtest assessment flow."""

    def __init__(self, return_data=None, raise_exc=None):
        self._return_data = return_data
        self._raise_exc = raise_exc

    def run_backtest(self, strategy_name, symbol, timeframe, candles, initial_capital=10000.0):
        if self._raise_exc:
            raise self._raise_exc
        return self._return_data

    def describe(self):
        return {"name": "MockBacktestSource", "port": "BacktestSource", "connected": True}


class MockLabArtifactSource(LabArtifactSource):
    """Mock LabArtifactSource for testing presenter integration."""

    def __init__(self, signal_data=None, setup_data=None):
        self._signal = signal_data
        self._setup = setup_data

    def connect(self):
        pass

    def fetch_signal(self, symbol: str, timeframe: str):
        return self._signal

    def fetch_trade_setup(self, symbol: str, timeframe: str):
        return self._setup

    def fetch_stability(self, strategy_name: str):
        return None

    def close(self):
        pass

    def describe(self):
        return {"name": "MockLabArtifactSource", "status": "active"}


class DummyMarketDataProvider(MarketDataProvider):
    """Dummy MarketDataProvider storing candles in memory for tests."""

    def __init__(self, provider_id: str = "biquote_provider", name: str = "BiQuote Market Data"):
        self.provider_id = provider_id
        self._name = name
        self._candles = {}
        self.connected = True

    def connect(self) -> None:
        self.connected = True

    def close(self) -> None:
        self.connected = False

    def set_candles(self, symbol: str, timeframe: str, candles):
        self._candles[(symbol, timeframe)] = list(candles)

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100):
        candles = self._candles.get((symbol, timeframe), [])
        return [c.to_dict() if hasattr(c, "to_dict") else c for c in candles]

    def describe(self):
        return {"name": self._name, "id": self.provider_id, "status": "connected"}


@pytest.fixture
def provider_operations():
    registry = ProviderRegistry()
    mdp = DummyMarketDataProvider(provider_id="biquote_provider", name="BiQuote Market Data")
    qp = BiQuoteQuoteProvider()
    registry.register("biquote_provider", CATEGORY_MARKET_DATA, mdp)
    registry.register("biquote_quote", CATEGORY_QUOTE, qp)
    access = ProviderAccess(registry)

    candles = [
        Candle(timestamp=1700000000.0 + i * 3600, open=2000.0, high=2010.0, low=1990.0, close=2005.0, volume=100.0)
        for i in range(20)
    ]
    mdp.set_candles("XAUUSD", "1h", candles)

    return ProviderOperations(access)


def test_valid_backtest_assessment_flow(provider_operations):
    bt_source = MockBacktestSource(
        return_data={
            "strategy_name": "GoldTrendv1",
            "symbol": "XAUUSD",
            "timeframe": "1h",
            "total_trades": 50,
            "win_rate": 0.60,
            "profit_factor": 1.80,
            "max_drawdown": 0.12,
            "net_profit": 8500.0,
                "detail": "backtest with api_key=12345 completed",
        }
    )
    svc = BacktestAssessmentService(operations=provider_operations, backtest_source=bt_source)
    res = svc.run_assessment("GoldTrendv1", "XAUUSD", "1h", "biquote_provider")

    assert res.strategy_name == "GoldTrendv1"
    assert res.total_trades == 50
    assert res.win_rate == 0.60
    assert res.stability is not None
    assert res.stability.risk_level == "medium"
    assert "[REDACTED]" in res.detail


def test_empty_backtest_assessment_flow(provider_operations):
    # Fetch for symbol with no candles
    bt_source = MockBacktestSource(return_data=None)
    svc = BacktestAssessmentService(operations=provider_operations, backtest_source=bt_source)
    res = svc.run_assessment("GoldTrendv1", "EURUSD", "1h", "biquote_provider")

    assert res.total_trades == 0
    assert res.win_rate == 0.0
    assert res.detail.startswith("empty:")


def test_unavailable_upstream_backtest_assessment_flow(provider_operations):
    bt_source = MockBacktestSource(return_data=None)
    svc = BacktestAssessmentService(operations=provider_operations, backtest_source=bt_source)
    res = svc.run_assessment("GoldTrendv1", "XAUUSD", "1h", "biquote_provider")

    assert res.total_trades == 0
    assert res.detail.startswith("unavailable:")


def test_invalid_data_backtest_assessment_flow(provider_operations):
    # Malformed data (missing win_rate)
    bt_source = MockBacktestSource(return_data={"total_trades": 10})
    svc = BacktestAssessmentService(operations=provider_operations, backtest_source=bt_source)
    res = svc.run_assessment("GoldTrendv1", "XAUUSD", "1h", "biquote_provider")

    assert res.total_trades == 0
    assert res.detail.startswith("invalid:")


def test_application_failure_backtest_assessment_flow(provider_operations):
    bt_source = MockBacktestSource(raise_exc=RuntimeError("Engine crash with api_key=xyz"))
    svc = BacktestAssessmentService(operations=provider_operations, backtest_source=bt_source)
    res = svc.run_assessment("GoldTrendv1", "XAUUSD", "1h", "biquote_provider")

    assert res.total_trades == 0
    assert res.detail.startswith("failed:")
    assert "[REDACTED]" in res.detail


def test_authorization_failure_backtest_assessment_flow(provider_operations):
    bt_source = MockBacktestSource(return_data={"total_trades": 10, "win_rate": 0.5, "profit_factor": 1.2, "max_drawdown": 0.1, "net_profit": 100})
    svc = BacktestAssessmentService(operations=provider_operations, backtest_source=bt_source)

    guest_user = UserAuthorization(user_id="guest1", role=UserRole.GUEST, permissions=set(), auth_code="guestpass")
    res = svc.run_assessment("GoldTrendv1", "XAUUSD", "1h", "biquote_provider", user=guest_user)

    assert res.total_trades == 0
    assert res.detail.startswith("unauthorized:")


def test_presenter_snapshot_backtest_integration_user_isolation(provider_operations):
    from src.platform.integrations.project1 import Project1IntegrationPort
    from src.platform.domain.presented_signal import PresentedSignal
    import time

    class MockConnectedPort(Project1IntegrationPort):
        def fetch_latest_signal(self, symbol, timeframe, strategy_name=None):
            return PresentedSignal(
                signal_id="sig_test_bt",
                symbol=symbol,
                signal_type="buy",
                timestamp=time.time(),
                confidence=0.85,
                strategy_name="GoldTrendv1",
                timeframe=timeframe,
                metadata={"provenance_type": "live_signal"},
            )
        def describe(self):
            return {"name": "MockConnectedPort", "port": "Project1IntegrationPort", "connected": True}

    adapter = MockConnectedPort()

    bt_source = MockBacktestSource(
        return_data={
            "strategy_name": "GoldTrendv1",
            "symbol": "XAUUSD",
            "timeframe": "1h",
            "total_trades": 40,
            "win_rate": 0.65,
            "profit_factor": 2.0,
            "max_drawdown": 0.10,
            "net_profit": 12000.0,
                "detail": "api_key=999 used for backtest execution",
        }
    )
    bt_service = BacktestAssessmentService(operations=provider_operations, backtest_source=bt_source)

    presenter = Project1SignalPresenter(port=adapter, backtest_service=bt_service)

    # Admin snapshot gets full detail
    admin_user = UserAuthorization(user_id="admin1", role=UserRole.ADMIN, permissions={Permission.ADMIN_ALL}, auth_code="adminpass")
    admin_snap = presenter.build_host_snapshot("XAUUSD", "1h", user=admin_user)
    assert admin_snap["performance"]["status"] == "available"
    assert "[REDACTED]" in admin_snap["performance"]["data"]["detail"]

    # Normal user snapshot filters protected payload
    normal_user = UserAuthorization(user_id="user1", role=UserRole.USER, permissions={Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS}, auth_code="userpass")
    user_snap = presenter.build_host_snapshot("XAUUSD", "1h", user=normal_user)
    assert user_snap["performance"]["status"] == "available"
    assert "[REDACTED]" in user_snap["performance"]["data"]["detail"]

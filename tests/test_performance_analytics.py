"""Tests for PerformanceAnalyticsService and performance/risk API endpoints."""

import pytest
from src.platform.adapters.project1_adapter import Project1LabArtifactAdapter, DisconnectedProject1Adapter, LabArtifactBacktestAdapter
from src.platform.domain.security import Permission
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.integrations.lab import LabArtifactSource
from src.platform.providers.biquote import BiQuoteProvider
from src.platform.providers.biquote_quote import BiQuoteQuoteProvider
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.backtest_assessment import BacktestAssessmentService
from src.platform.services.lab_artifacts import LabArtifactService
from src.platform.services.performance_analytics import PerformanceAnalyticsService
from src.platform.services.provider_access import ProviderAccess
from src.platform.services.provider_operations import ProviderOperations
from src.platform.services.provider_registry import ProviderRegistry
from src.platform.services.security import SecurityBoundaryService


class DummyLabSource(LabArtifactSource):
    def __init__(self):
        self.connected = True

    def connect(self) -> None:
        self.connected = True

    def close(self) -> None:
        self.connected = False

    def describe(self) -> dict:
        return {"name": "DummyLabSource", "connected": self.connected}

    def fetch_signal(self, symbol: str, timeframe: str) -> dict:
        return {"action": "buy", "strategy_name": "GoldTrendv1", "timestamp": 1700000000, "confidence": 0.85}

    def fetch_trade_setup(self, symbol: str, timeframe: str) -> dict:
        return {"entry_price": 2650.0, "stop_loss": 2630.0, "take_profit_1": 2680.0, "take_profit_2": 2700.0, "take_profit_3": 2720.0}

    def fetch_stability(self, symbol: str, timeframe: str) -> dict:
        return {"score": 0.85, "risk_level": "low"}


@pytest.fixture
def test_user() -> UserAuthorization:
    return UserAuthorization(
        user_id="user_test_perf",
        auth_code="code123",
        telegram_chat_id="chat123",
        permissions={Permission.READ_SIGNALS, Permission.READ_STRATEGY_PARAMETERS, Permission.READ_TRADE_SETUPS},
    )


@pytest.fixture
def performance_service() -> PerformanceAnalyticsService:
    src = DummyLabSource()
    lab_service = LabArtifactService(source=src)
    port = Project1LabArtifactAdapter(service=lab_service)
    bt_source = LabArtifactBacktestAdapter(service=lab_service)

    reg = ProviderRegistry()
    reg.register(provider_id="biquote_provider", category="market_data", provider=BiQuoteProvider())
    reg.register(provider_id="biquote_provider", category="quote", provider=BiQuoteQuoteProvider())
    access = ProviderAccess(registry=reg)
    ops = ProviderOperations(access=access)

    security = SecurityBoundaryService()
    audit = PlatformAuditControlService(security_boundary=security)
    backtest = BacktestAssessmentService(operations=ops, backtest_source=bt_source, security_service=security)

    return PerformanceAnalyticsService(
        backtest_service=backtest,
        port=port,
        security_service=security,
        audit_control_service=audit,
    )


def test_evaluate_performance_success(performance_service, test_user):
    summary = performance_service.evaluate_performance(
        strategy_name="GoldTrendv1",
        symbol="XAUUSD",
        timeframe="1h",
        user=test_user,
    )
    assert summary is not None
    assert summary.strategy_name == "GoldTrendv1"
    assert summary.symbol == "XAUUSD"
    assert summary.timeframe == "1h"
    assert summary.drawdown_profile is not None
    assert summary.risk_profile is not None


def test_evaluate_performance_disconnected(test_user):
    src = DummyLabSource()
    lab_service = LabArtifactService(source=src)
    bt_source = LabArtifactBacktestAdapter(service=lab_service)

    reg = ProviderRegistry()
    reg.register(provider_id="biquote_provider", category="market_data", provider=BiQuoteProvider())
    reg.register(provider_id="biquote_provider", category="quote", provider=BiQuoteQuoteProvider())
    access = ProviderAccess(registry=reg)
    ops = ProviderOperations(access=access)

    port = DisconnectedProject1Adapter()
    security = SecurityBoundaryService()
    backtest = BacktestAssessmentService(operations=ops, backtest_source=bt_source, security_service=security)
    perf_service = PerformanceAnalyticsService(
        backtest_service=backtest,
        port=port,
        security_service=security,
    )
    summary = perf_service.evaluate_performance(
        strategy_name="GoldTrendv1",
        symbol="XAUUSD",
        timeframe="1h",
        user=test_user,
    )
    assert summary.status == "disconnected"
    assert summary.detail != ""


def test_performance_summary_to_dict(performance_service, test_user):
    summary = performance_service.evaluate_performance(
        strategy_name="GoldTrendv1",
        symbol="XAUUSD",
        timeframe="1h",
        user=test_user,
    )
    d = summary.to_dict()
    assert isinstance(d, dict)
    assert d["strategy_name"] == "GoldTrendv1"
    assert "drawdown_profile" in d
    assert "risk_profile" in d

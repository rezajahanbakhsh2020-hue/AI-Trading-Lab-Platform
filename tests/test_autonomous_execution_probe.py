"""Probe test verifying full autonomous execution authorization workflow (Part 15)."""

from typing import Any, Dict, List, Optional

from src.platform.domain.autonomous_authorization import AUTHORIZATION_STATUS_AUTHORIZED
from src.platform.domain.market import Candle
from src.platform.domain.quote import Quote
from src.platform.domain.readiness import Readiness
from src.platform.domain.stability import Stability
from src.platform.domain.strategy_result import StrategyResult
from src.platform.domain.trade_readiness import TradeReadiness
from src.platform.domain.trade_setup import TradeSetup
from src.platform.providers.market_data import MarketDataProvider
from src.platform.providers.quote import QuoteProvider
from src.platform.services.autonomous_authorization import AutonomousAuthorizationService
from src.platform.services.provider_access import ProviderAccess
from src.platform.services.provider_monitoring import ProviderMonitor
from src.platform.services.provider_operations import ProviderOperations
from src.platform.services.provider_readiness import ProviderReadinessService
from src.platform.services.provider_registry import (
    CATEGORY_MARKET_DATA,
    CATEGORY_QUOTE,
    ProviderRegistry,
)
from src.platform.services.provider_selection import ProviderSelectionService
from src.platform.services.trade_signal import TradeSignalService


class ProbeMarketDataProvider(MarketDataProvider):
    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "Probe Market Data",
            "status": "healthy",
            "supports_fetch_candles": True,
            "supported_symbols": ["XAUUSD"],
            "supported_timeframes": ["1h"],
        }

    def fetch_candles(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        return [
            {
                "timestamp": 1000.0,
                "open": 2000.0,
                "high": 2010.0,
                "low": 1995.0,
                "close": 2005.0,
                "volume": 100.0,
            }
        ]


class ProbeQuoteProvider(QuoteProvider):
    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "Probe Quote",
            "status": "healthy",
            "supports_fetch_quote": True,
            "supported_symbols": ["XAUUSD"],
        }

    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "timestamp": 1000.0,
            "bid": 2000.0,
            "ask": 2000.5,
        }


def test_autonomous_execution_probe():
    """Verify full end-to-end autonomous authorization pipeline integration."""

    # 1. Setup Provider Registry & Services
    registry = ProviderRegistry()
    md_provider = ProbeMarketDataProvider()
    qp_provider = ProbeQuoteProvider()
    registry.register("md_probe", CATEGORY_MARKET_DATA, md_provider)
    registry.register("qp_probe", CATEGORY_QUOTE, qp_provider)

    access = ProviderAccess(registry)
    ops = ProviderOperations(access)
    monitor = ProviderMonitor(ops)
    readiness_svc = ProviderReadinessService(access, monitor=monitor)
    selection_svc = ProviderSelectionService(readiness_svc)

    # 2. Operational Provider Selection
    provider_sel = selection_svc.select_provider(CATEGORY_MARKET_DATA, preferred_provider_id="md_probe")
    assert provider_sel.is_selected is True
    assert provider_sel.selected_provider_id == "md_probe"

    # 3. Strategy Result & Signal Engine
    setup = TradeSetup(
        symbol="XAUUSD",
        entry_price=2000.0,
        stop_loss=1990.0,
        take_profit_1=2020.0,
        take_profit_2=2030.0,
        take_profit_3=2040.0,
        timestamp=1000.0,
        direction="buy",
    )
    strategy_result = StrategyResult(
        strategy_name="ProbeStrategy",
        timestamp=1000.0,
        proposed_action="buy",
        stability=Stability(score=0.9, risk_level="low"),
        readiness=Readiness(approved=True, timestamp=1000.0),
        trade_setup=setup,
    )

    signal_svc = TradeSignalService()
    trade_signal = signal_svc.generate(strategy_result)
    assert trade_signal.tradable is True

    # 4. Real Market Trade Readiness Assessment
    readiness = TradeReadiness(
        symbol="XAUUSD",
        timeframe="1h",
        direction="buy",
        entry_price=2000.0,
        stop_loss=1990.0,
        take_profit_1=2020.0,
        take_profit_2=2030.0,
        take_profit_3=2040.0,
        current_price=2000.5,
        entry_distance_absolute=0.5,
        entry_distance_percent=0.025,
        stop_distance_absolute=-10.5,
        stop_distance_percent=-0.525,
        tp1_distance_percent=0.975,
        tp2_distance_percent=1.475,
        tp3_distance_percent=1.975,
        risk_reward_to_tp1=2.0,
        levels_are_sane=True,
    )
    assert readiness.levels_are_sane is True

    # 5. Full Autonomous Execution Authorization
    auth_svc = AutonomousAuthorizationService()
    authorization = auth_svc.authorize(
        trade_signal=trade_signal,
        provider_selection=provider_sel,
        trade_readiness=readiness,
        min_risk_reward_to_tp1=1.5,
        require_selected_provider=True,
    )

    assert authorization.status == AUTHORIZATION_STATUS_AUTHORIZED
    assert authorization.is_authorized is True
    assert authorization.trade_signal.signal.action == "buy"
    assert authorization.provider_selection.selected_provider_id == "md_probe"
    assert authorization.trade_readiness.levels_are_sane is True

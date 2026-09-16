"""Project 1 Integration Port Adapters.

Adapts LabArtifactService / LabArtifactSource outputs into PresentedSignal domain
objects for consumption by Project 2 host application services and UI layer.

Rules:
- Read-only: Never mutates or imports Project 1 internals.
- Data integrity: Preserves signal_id, symbol, action, timestamp, confidence,
  strategy_name, timeframe, and trade setup prices (entry, stop_loss, take_profits).
- Honest unavailable handling: Returns None when Project 1 output is missing or disconnected.
"""

from typing import Any, Dict, Optional

from typing import Sequence
from src.platform.domain.market import Candle
from src.platform.domain.presented_signal import PresentedSignal
from src.platform.integrations.backtest import BacktestSource
from src.platform.integrations.project1 import Project1IntegrationPort
from src.platform.services.lab_artifacts import LabArtifactService


class LabArtifactBacktestAdapter(BacktestSource):
    """Adapter bridging LabArtifactService to BacktestSource port."""

    def __init__(self, service: LabArtifactService) -> None:
        if service is None or not isinstance(service, LabArtifactService):
            raise ValueError("service must be a valid LabArtifactService")
        self._service = service

    def run_backtest(
        self,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        candles: Sequence[Candle],
        initial_capital: float = 10000.0,
    ) -> Optional[Dict[str, Any]]:
        # Read stability/backtest metrics from LabArtifactService
        stability = self._service.get_stability(strategy_name=strategy_name)
        if stability is None or not stability.metrics:
            return None

        m = stability.metrics
        return {
            "strategy_name": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "total_trades": int(m.get("total_trades", 0)),
            "win_rate": float(m.get("win_rate", 0.0)),
            "profit_factor": float(m.get("profit_factor", 0.0)),
            "max_drawdown": float(m.get("max_drawdown", 0.0)),
            "net_profit": float(m.get("net_profit", 0.0)),
        }

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "LabArtifactBacktestAdapter",
            "port": "BacktestSource",
            "connected": True,
            "source": self._service._source.describe(),
        }


class Project1LabArtifactAdapter(Project1IntegrationPort):
    """Adapter bridging LabArtifactService to Project1IntegrationPort."""

    def __init__(self, service: LabArtifactService) -> None:
        if service is None or not isinstance(service, LabArtifactService):
            raise ValueError("service must be a valid LabArtifactService")
        self._service = service

    def fetch_latest_signal(
        self, symbol: str, timeframe: str, strategy_name: Optional[str] = None
    ) -> Optional[PresentedSignal]:
        signal = self._service.get_signal(symbol=symbol, timeframe=timeframe)
        if signal is None:
            return None

        if strategy_name is not None and signal.strategy_name != strategy_name:
            return None

        setup = self._service.get_trade_setup(symbol=symbol, timeframe=timeframe)

        take_profits = ()
        entry_price = None
        stop_loss = None

        if setup is not None:
            entry_price = setup.entry_price
            stop_loss = setup.stop_loss
            tps = []
            if setup.take_profit_1 is not None:
                tps.append(setup.take_profit_1)
            if setup.take_profit_2 is not None:
                tps.append(setup.take_profit_2)
            if setup.take_profit_3 is not None:
                tps.append(setup.take_profit_3)
            take_profits = tuple(tps)

        signal_id = f"p1_{symbol.lower()}_{timeframe.lower()}_{int(signal.timestamp)}"

        return PresentedSignal(
            signal_id=signal_id,
            symbol=symbol,
            signal_type=signal.action.lower(),
            timestamp=float(signal.timestamp),
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profits=take_profits,
            confidence=signal.confidence,
            strategy_name=signal.strategy_name,
            timeframe=timeframe,
            metadata={"source": "Project1", "adapter": "Project1LabArtifactAdapter"},
        )

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "Project1LabArtifactAdapter",
            "port": "Project1IntegrationPort",
            "connected": True,
            "source": self._service._source.describe(),
        }


class DisconnectedProject1Adapter(Project1IntegrationPort):
    """Placeholder adapter for Project1IntegrationPort when Project 1 is disconnected."""

    def fetch_latest_signal(
        self, symbol: str, timeframe: str, strategy_name: Optional[str] = None
    ) -> Optional[PresentedSignal]:
        return None

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "DisconnectedProject1Adapter",
            "port": "Project1IntegrationPort",
            "connected": False,
            "status": "disconnected",
            "message": "No Project 1 data connected yet.",
        }

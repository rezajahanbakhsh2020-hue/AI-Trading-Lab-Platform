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

    def run_walk_forward_validation(
        self,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        candles: Sequence[Candle],
        initial_capital: float = 10000.0,
        window_count: int = 3,
    ) -> Optional[Dict[str, Any]]:
        wf = self._service.get_walk_forward(strategy_name=strategy_name, symbol=symbol, timeframe=timeframe)
        if wf is None:
            return None

        return wf.to_dict()

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "LabArtifactBacktestAdapter",
            "port": "BacktestSource",
            "connected": True,
            "source": self._service._source.describe(),
        }


class Project1LabArtifactAdapter:
    """Historical artifact inspection adapter for LabArtifactService.

    ARCHITECTURAL BOUNDARY MANDATE:
    This adapter accesses historical laboratory artifacts, fixtures, and backtest datasets.
    It DOES NOT implement Project1IntegrationPort and MUST NEVER satisfy the production
    Current Live Signal Feed port. It is strictly available for historical research, backtest,
    and development inspection.
    """

    def __init__(self, service: LabArtifactService) -> None:
        if service is None or not isinstance(service, LabArtifactService):
            raise ValueError("service must be a valid LabArtifactService")
        self._service = service

    def fetch_historical_artifact(
        self, symbol: str, timeframe: str, strategy_name: Optional[str] = None
    ) -> Optional[PresentedSignal]:
        """Fetch historical artifact record for laboratory inspection / backtest context."""
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
            metadata={
                "source": "Project1",
                "adapter": "Project1LabArtifactAdapter",
                "provenance_type": "lab_artifact",
                "is_historical": True,
            },
        )

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "Project1LabArtifactAdapter",
            "port": "HistoricalLabArtifactPort",
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


class Project1GatewayAdapter(Project1IntegrationPort):
    """Adapter bridging Project1IntegrationGatewayService / Project1IntegrationRepositoryPort to Project1IntegrationPort."""

    def __init__(self, gateway_service: Any) -> None:
        if gateway_service is None:
            raise ValueError("gateway_service must be provided")
        self._gateway_service = gateway_service

    def fetch_latest_signal(
        self, symbol: str, timeframe: str, strategy_name: Optional[str] = None
    ) -> Optional[PresentedSignal]:
        import time
        repo = getattr(self._gateway_service, "_repo", None)
        if repo is None:
            return None

        records = repo.list_records_for_user(
            user_id=None,
            symbol=symbol,
            lifecycle_state=None,
            limit=100,
        )

        if not records:
            return None

        target_rec = None
        for rec in records:
            if timeframe and rec.get("timeframe") and rec.get("timeframe") != timeframe:
                continue
            if strategy_name and rec.get("strategy_name") and rec.get("strategy_name") != strategy_name:
                continue
            target_rec = rec
            break

        if target_rec is None:
            return None

        tps = []
        if target_rec.get("take_profit_1") is not None:
            tps.append(float(target_rec["take_profit_1"]))
        if target_rec.get("take_profit_2") is not None:
            tps.append(float(target_rec["take_profit_2"]))
        if target_rec.get("take_profit_3") is not None:
            tps.append(float(target_rec["take_profit_3"]))

        raw_meta = target_rec.get("metadata")
        meta = dict(raw_meta) if isinstance(raw_meta, dict) else {}
        if "provenance_type" not in meta:
            meta["provenance_type"] = "live_signal"
        meta["adapter"] = "Project1GatewayAdapter"
        meta["source"] = "Project1"

        sig_event_ts = float(target_rec.get("timestamp") or time.time())
        ingested_ts = float(target_rec.get("created_at") or time.time())
        meta["signal_timestamp"] = sig_event_ts
        meta["ingested_at"] = ingested_ts

        return PresentedSignal(
            signal_id=str(target_rec.get("signal_id") or f"p1_{symbol.lower()}_{int(sig_event_ts)}"),
            symbol=symbol,
            signal_type=str(target_rec.get("signal_type", "no-signal")).lower(),
            timestamp=sig_event_ts,
            entry_price=float(target_rec["entry_price"]) if target_rec.get("entry_price") is not None else None,
            stop_loss=float(target_rec["stop_loss"]) if target_rec.get("stop_loss") is not None else None,
            take_profits=tuple(tps),
            confidence=float(target_rec["confidence"]) if target_rec.get("confidence") is not None else None,
            strategy_name=target_rec.get("strategy_name"),
            timeframe=timeframe,
            metadata=meta,
        )

    def describe(self) -> Dict[str, Any]:
        repo = getattr(self._gateway_service, "_repo", None)
        recs = repo.list_records_for_user(user_id=None, limit=1) if repo else []
        has_records = len(recs) > 0
        return {
            "name": "Project1GatewayAdapter",
            "port": "Project1IntegrationPort",
            "connected": has_records,
            "status": "active" if has_records else "disconnected",
            "message": "Connected to Project 1 Integration Gateway." if has_records else "No Project 1 integration records received yet via gateway.",
        }

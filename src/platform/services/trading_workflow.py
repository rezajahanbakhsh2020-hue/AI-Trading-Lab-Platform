"""Trading workflow application service (Part 16: Cross-Domain Trading Flow).

Orchestrates a deterministic, cross-domain trading workflow connecting Provider
Selection, Signal Evaluation, Trade Readiness, Trade Signal Generation, and
Autonomous Authorization boundaries.

Rules:
- Strictly deterministic pure application boundary (no I/O, no network calls).
- Performs no price, signal, confidence, or risk data fabrication.
- Integrates existing services cleanly via constructor injection.
"""

from typing import Optional, Union

from src.platform.domain.trading_workflow import (
    WORKFLOW_STATUS_DENIED,
    WORKFLOW_STATUS_EXECUTED,
    WORKFLOW_STATUS_NOT_READY,
    TradingWorkflowResult,
)

from src.platform.domain.readiness import Readiness
from src.platform.domain.stability import Stability
from src.platform.domain.strategy_result import StrategyResult
from src.platform.services.autonomous_authorization import AutonomousAuthorizationService
from src.platform.services.provider_selection import ProviderSelectionService
from src.platform.services.signal_engine import SignalEngineService
from src.platform.services.trade_readiness import TradeReadinessService
from src.platform.services.trade_signal import TradeSignalService

REASON_WORKFLOW_EXECUTED = "trading workflow authorized and executed"
REASON_WORKFLOW_DENIED = "trading workflow authorization denied"
REASON_PROVIDER_NOT_READY = "required provider selection is not ready or unavailable"


class TradingWorkflowService:
    """Application service orchestrating a deterministic cross-domain trading workflow."""

    def __init__(
        self,
        authorization_service: AutonomousAuthorizationService,
        selection_service: Optional[ProviderSelectionService] = None,
        readiness_service: Optional[TradeReadinessService] = None,
        trade_signal_service: Optional[TradeSignalService] = None,
        signal_engine_service: Optional[SignalEngineService] = None,
    ) -> None:
        if authorization_service is None or not isinstance(
            authorization_service, AutonomousAuthorizationService
        ):
            raise ValueError("authorization_service must be an AutonomousAuthorizationService instance")

        self._auth_svc = authorization_service
        self._selection_svc = selection_service
        self._readiness_svc = readiness_service
        self._trade_signal_svc = trade_signal_service or TradeSignalService()
        self._signal_engine_svc = signal_engine_service

    def run_workflow(
        self,
        symbol: str,
        timeframe: str,
        strategy_result: Optional[StrategyResult] = None,
        preferred_provider_id: Optional[str] = None,
        candles_provider_id: Optional[str] = None,
        quote_provider_id: Optional[str] = None,
        timestamp: Optional[Union[int, float]] = None,
        min_risk_reward_to_tp1: Optional[float] = None,
        require_selected_provider: bool = False,
    ) -> TradingWorkflowResult:
        """Execute cross-domain trading workflow deterministically."""

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol must be a non-empty string")

        if not isinstance(timeframe, str) or not timeframe.strip():
            raise ValueError("timeframe must be a non-empty string")

        # 1. Operational Provider Selection
        provider_sel = None
        if self._selection_svc is not None:
            provider_sel = self._selection_svc.select_provider(
                category="market_data",
                preferred_provider_id=preferred_provider_id,
                symbol=symbol,
                timeframe=timeframe,
            )

        if require_selected_provider and (provider_sel is None or not provider_sel.is_selected):
            reason = (
                f"{REASON_PROVIDER_NOT_READY}: "
                f"{provider_sel.reason if provider_sel else 'provider selection unavailable'}"
            )
            eval_ts = float(timestamp) if timestamp is not None else 0.0
            dummy_res = StrategyResult(
                strategy_name="WorkflowStrategy",
                timestamp=eval_ts,
                proposed_action="no-signal",
                stability=Stability(score=0.0, risk_level="high"),
                readiness=Readiness(approved=False, reason=reason, timestamp=eval_ts),
            )
            dummy_sig = self._trade_signal_svc.generate(dummy_res)
            auth = self._auth_svc.authorize(
                trade_signal=dummy_sig,
                provider_selection=provider_sel,
                timestamp=eval_ts,
            )
            return TradingWorkflowResult(
                symbol=symbol,
                timeframe=timeframe,
                status=WORKFLOW_STATUS_NOT_READY,
                reason=reason,
                timestamp=eval_ts,
                authorization=auth,
                trade_signal=dummy_sig,
                provider_selection=provider_sel,
            )

        # 2. Strategy Signal Evaluation
        if strategy_result is None:
            eval_ts = float(timestamp) if timestamp is not None else 0.0
            strategy_result = StrategyResult(
                strategy_name="WorkflowStrategy",
                timestamp=eval_ts,
                proposed_action="no-signal",
                stability=Stability(score=0.0, risk_level="high"),
                readiness=Readiness(approved=False, reason="no strategy result provided", timestamp=eval_ts),
            )

        trade_sig = self._trade_signal_svc.generate(strategy_result)

        # 3. Trade Readiness Assessment
        trade_readiness = None
        if self._readiness_svc is not None and candles_provider_id is not None:
            readiness_res = self._readiness_svc.assess(
                symbol=symbol,
                timeframe=timeframe,
                candles_provider_id=candles_provider_id,
                quote_provider_id=quote_provider_id,
                strategy_name=strategy_result.strategy_name,
            )
            trade_readiness = readiness_res.trade_readiness

        # 4. Autonomous Authorization
        eval_ts = float(timestamp) if timestamp is not None else float(strategy_result.timestamp)
        auth = self._auth_svc.authorize(
            trade_signal=trade_sig,
            provider_selection=provider_sel,
            trade_readiness=trade_readiness,
            timestamp=eval_ts,
            min_risk_reward_to_tp1=min_risk_reward_to_tp1,
            require_selected_provider=require_selected_provider,
        )

        status = (
            WORKFLOW_STATUS_EXECUTED
            if auth.is_authorized
            else WORKFLOW_STATUS_DENIED
        )
        reason = (
            REASON_WORKFLOW_EXECUTED
            if auth.is_authorized
            else f"{REASON_WORKFLOW_DENIED}: {auth.reason}"
        )

        return TradingWorkflowResult(
            symbol=symbol,
            timeframe=timeframe,
            status=status,
            reason=reason,
            timestamp=eval_ts,
            authorization=auth,
            trade_signal=trade_sig,
            provider_selection=provider_sel,
            trade_readiness=trade_readiness,
        )

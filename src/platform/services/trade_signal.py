"""Trade-signal application service.

Turns an already-evaluated StrategyResult into a TradeSignal.

This service does not:
- fetch market data
- run strategies
- invent prices, signals, or stability scores
- bypass readiness or stability gates
- perform I/O

BUY/SELL is emitted only when readiness is approved, stability risk is
not high/critical, the proposed action is buy or sell, and a matching
TradeSetup is present. Otherwise a deterministic no-signal result is
returned.
"""

from typing import Optional

from src.platform.domain.signal import Signal
from src.platform.domain.strategy_result import StrategyResult
from src.platform.domain.trade_signal import TradeSignal

UNSTABLE_RISK_LEVELS = frozenset(("high", "critical"))


class TradeSignalService:
    """Deterministic conversion of a StrategyResult into a TradeSignal."""

    def generate(self, result: StrategyResult) -> TradeSignal:
        if not isinstance(result, StrategyResult):
            raise ValueError("result must be a StrategyResult instance")

        blocked = self._block_reason(result)
        if blocked is not None:
            return self._no_signal(result, blocked)

        setup = result.trade_setup
        return TradeSignal(
            signal=Signal(
                action=result.proposed_action,
                strategy_name=result.strategy_name,
                timestamp=result.timestamp,
                confidence=result.stability.score,
            ),
            readiness=result.readiness,
            stability=result.stability,
            reason="trade signal approved",
            tradable=True,
            trade_setup=setup,
        )

    def _block_reason(self, result: StrategyResult) -> Optional[str]:
        if not result.readiness.approved:
            return result.readiness.reason or "strategy is not trade-ready"
        if result.stability.risk_level in UNSTABLE_RISK_LEVELS:
            return "strategy stability risk is " + result.stability.risk_level
        if result.proposed_action in ("hold", "no-signal"):
            return "proposed action is " + result.proposed_action
        if result.trade_setup is None:
            return "trade setup is unavailable"
        if result.trade_setup.direction != result.proposed_action:
            return "trade setup direction does not match proposed action"
        return None

    def _no_signal(self, result: StrategyResult, reason: str) -> TradeSignal:
        return TradeSignal(
            signal=Signal(
                action="no-signal",
                strategy_name=result.strategy_name,
                timestamp=result.timestamp,
                confidence=None,
            ),
            readiness=result.readiness,
            stability=result.stability,
            reason=reason,
            tradable=False,
            trade_setup=None,
        )

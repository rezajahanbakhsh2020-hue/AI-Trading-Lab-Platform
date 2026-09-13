"""Strategy validation application service (Part 18: Strategy Validation Flow).

Evaluates a strategy's backtest performance and stability assessment against
platform validation thresholds to produce a ValidatedStrategyState.

Rules:
- Strictly deterministic, pure application boundary (no I/O, no network calls).
- Performs no data, metric, or signal fabrication.
- Unavailable/missing backtest results yield UNVALIDATED/REJECTED state cleanly.
"""

from typing import Optional, Union

from src.platform.domain.backtest import BacktestResult
from src.platform.domain.stability import Stability
from src.platform.domain.trade_setup import TradeSetup
from src.platform.domain.validated_strategy import (
    STRATEGY_STATUS_REJECTED,
    STRATEGY_STATUS_UNVALIDATED,
    STRATEGY_STATUS_VALIDATED,
    ValidatedStrategyState,
)

REASON_VALIDATED = "strategy validated successfully"
REASON_NO_BACKTEST = "backtest result is missing or unavailable"
REASON_NO_TRADES = "backtest contains insufficient trades for validation"
REASON_HIGH_DRAWDOWN = "backtest drawdown exceeds maximum allowable threshold"
REASON_LOW_WIN_RATE = "backtest win rate is below required minimum"
REASON_UNSTABLE_RISK = "strategy stability risk level is unacceptably high"


class StrategyValidationService:
    """Application service for validating strategy backtests and stability."""

    def validate(
        self,
        strategy_name: str,
        backtest_result: Optional[BacktestResult] = None,
        trade_setup: Optional[TradeSetup] = None,
        min_win_rate: float = 0.50,
        max_drawdown: float = 0.25,
        min_trades: int = 5,
        allowed_risk_levels: tuple = ("low", "medium"),
        timestamp: Optional[Union[int, float]] = None,
    ) -> ValidatedStrategyState:
        """Deterministically evaluate backtest and stability against validation rules."""

        if not isinstance(strategy_name, str) or not strategy_name.strip():
            raise ValueError("strategy_name must be a non-empty string")
        clean_name = strategy_name.strip()

        eval_ts = float(timestamp) if timestamp is not None else 0.0

        if backtest_result is None:
            return ValidatedStrategyState(
                strategy_name=clean_name,
                status=STRATEGY_STATUS_UNVALIDATED,
                reason=REASON_NO_BACKTEST,
                timestamp=eval_ts,
                trade_setup=trade_setup,
            )

        if backtest_result.total_trades < min_trades:
            return ValidatedStrategyState(
                strategy_name=clean_name,
                status=STRATEGY_STATUS_REJECTED,
                reason=f"{REASON_NO_TRADES} ({backtest_result.total_trades} < {min_trades})",
                timestamp=eval_ts,
                backtest_result=backtest_result,
                stability=backtest_result.stability,
                trade_setup=trade_setup,
            )

        if backtest_result.max_drawdown > max_drawdown:
            return ValidatedStrategyState(
                strategy_name=clean_name,
                status=STRATEGY_STATUS_REJECTED,
                reason=f"{REASON_HIGH_DRAWDOWN} ({backtest_result.max_drawdown:.2f} > {max_drawdown:.2f})",
                timestamp=eval_ts,
                backtest_result=backtest_result,
                stability=backtest_result.stability,
                trade_setup=trade_setup,
            )

        if backtest_result.win_rate < min_win_rate:
            return ValidatedStrategyState(
                strategy_name=clean_name,
                status=STRATEGY_STATUS_REJECTED,
                reason=f"{REASON_LOW_WIN_RATE} ({backtest_result.win_rate:.2f} < {min_win_rate:.2f})",
                timestamp=eval_ts,
                backtest_result=backtest_result,
                stability=backtest_result.stability,
                trade_setup=trade_setup,
            )

        if backtest_result.stability is not None:
            if backtest_result.stability.risk_level not in allowed_risk_levels:
                return ValidatedStrategyState(
                    strategy_name=clean_name,
                    status=STRATEGY_STATUS_REJECTED,
                    reason=f"{REASON_UNSTABLE_RISK}: {backtest_result.stability.risk_level}",
                    timestamp=eval_ts,
                    backtest_result=backtest_result,
                    stability=backtest_result.stability,
                    trade_setup=trade_setup,
                )

        return ValidatedStrategyState(
            strategy_name=clean_name,
            status=STRATEGY_STATUS_VALIDATED,
            reason=REASON_VALIDATED,
            timestamp=eval_ts,
            backtest_result=backtest_result,
            stability=backtest_result.stability,
            trade_setup=trade_setup,
        )

"""Backtest assessment application service (Part 17: Backtest Validation & Stability Flow).

Runs a strategy backtest using real observed market data fetched through
ProviderOperations and evaluates its performance against platform Stability
and risk assessment rules.

Rules:
- Strictly deterministic, pure application boundary (no I/O, no network calls).
- Performs no price, performance, or risk metric fabrication.
- Consumes real market candles and delegates backtest execution to BacktestSource.
- Integrates backtest performance directly into platform Stability assessment.
"""

from typing import Any, Dict, Optional

from src.platform.domain.backtest import BacktestResult
from src.platform.domain.stability import Stability
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.integrations.backtest import BacktestSource
from src.platform.services.provider_operations import ProviderOperations
from src.platform.services.security import SecretSanitizer, SecurityBoundaryService


class BacktestAssessmentService:
    """Application service for running strategy backtests and assessing stability."""

    def __init__(
        self,
        operations: ProviderOperations,
        backtest_source: BacktestSource,
        security_service: Optional[SecurityBoundaryService] = None,
    ) -> None:
        if operations is None or not isinstance(operations, ProviderOperations):
            raise ValueError("operations must be a ProviderOperations instance")
        if backtest_source is None or not isinstance(backtest_source, BacktestSource):
            raise ValueError("backtest_source must be a BacktestSource instance")
        if security_service is not None and not isinstance(
            security_service, SecurityBoundaryService
        ):
            raise ValueError("security_service must be a SecurityBoundaryService instance")

        self._operations = operations
        self._source = backtest_source
        self._security_service = security_service or SecurityBoundaryService()

    def run_assessment(
        self,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        market_data_provider_id: str,
        initial_capital: float = 10000.0,
        candles_limit: int = 100,
        user: Optional[UserAuthorization] = None,
    ) -> BacktestResult:
        """Run backtest over real candles and assess stability, enforcing authorization and security bounds."""

        _validate_string(strategy_name, "strategy_name")
        _validate_string(symbol, "symbol")
        _validate_string(timeframe, "timeframe")
        _validate_string(market_data_provider_id, "market_data_provider_id")

        if initial_capital <= 0:
            raise ValueError("initial_capital must be greater than zero")

        if user is not None:
            allowed, reason = self._security_service.authorize(user, "signals", action="read")
            if not allowed:
                return BacktestResult(
                    strategy_name=strategy_name,
                    symbol=symbol,
                    timeframe=timeframe,
                    total_trades=0,
                    win_rate=0.0,
                    profit_factor=0.0,
                    max_drawdown=0.0,
                    net_profit=0.0,
                    stability=Stability(score=0.0, risk_level="critical"),
                    detail=f"unauthorized: {reason}",
                )

        try:
            # 1. Fetch real candles from explicit market data provider
            candles_result = self._operations.fetch_candles(
                provider_id=market_data_provider_id,
                symbol=symbol,
                timeframe=timeframe,
                limit=candles_limit,
            )

            if not candles_result.candles:
                return BacktestResult(
                    strategy_name=strategy_name,
                    symbol=symbol,
                    timeframe=timeframe,
                    total_trades=0,
                    win_rate=0.0,
                    profit_factor=0.0,
                    max_drawdown=0.0,
                    net_profit=0.0,
                    stability=Stability(score=0.0, risk_level="critical"),
                    detail="empty: no candles available for backtest execution",
                )

            # 2. Execute backtest on external backtest source port
            raw_backtest = self._source.run_backtest(
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                candles=candles_result.candles,
                initial_capital=initial_capital,
            )

            if raw_backtest is None:
                return BacktestResult(
                    strategy_name=strategy_name,
                    symbol=symbol,
                    timeframe=timeframe,
                    total_trades=0,
                    win_rate=0.0,
                    profit_factor=0.0,
                    max_drawdown=0.0,
                    net_profit=0.0,
                    stability=Stability(score=0.0, risk_level="critical"),
                    detail="unavailable: backtest execution unavailable from source",
                )

            _require_dict(raw_backtest, "backtest")
            total_trades = int(_require_field(raw_backtest, "total_trades", "backtest"))
            win_rate = float(_require_field(raw_backtest, "win_rate", "backtest"))
            profit_factor = float(_require_field(raw_backtest, "profit_factor", "backtest"))
            max_drawdown = float(_require_field(raw_backtest, "max_drawdown", "backtest"))
            net_profit = float(_require_field(raw_backtest, "net_profit", "backtest"))

            # 3. Assess Stability & Risk Level based on backtest performance metrics
            stability = _assess_stability_from_backtest(
                win_rate=win_rate,
                profit_factor=profit_factor,
                max_drawdown=max_drawdown,
                net_profit=net_profit,
                total_trades=total_trades,
            )

            detail_msg = "backtest assessment completed successfully"
            if "detail" in raw_backtest and isinstance(raw_backtest["detail"], str):
                detail_msg = SecretSanitizer.sanitize_string(raw_backtest["detail"])

            return BacktestResult(
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                total_trades=total_trades,
                win_rate=win_rate,
                profit_factor=profit_factor,
                max_drawdown=max_drawdown,
                net_profit=net_profit,
                stability=stability,
                detail=detail_msg,
            )

        except ValueError as ve:
            return BacktestResult(
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                total_trades=0,
                win_rate=0.0,
                profit_factor=0.0,
                max_drawdown=0.0,
                net_profit=0.0,
                stability=Stability(score=0.0, risk_level="critical"),
                detail=f"invalid: {str(ve)}",
            )
        except Exception as exc:
            return BacktestResult(
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                total_trades=0,
                win_rate=0.0,
                profit_factor=0.0,
                max_drawdown=0.0,
                net_profit=0.0,
                stability=Stability(score=0.0, risk_level="critical"),
                detail=f"failed: {SecretSanitizer.sanitize_string(str(exc))}",
            )


def _assess_stability_from_backtest(
    win_rate: float,
    profit_factor: float,
    max_drawdown: float,
    net_profit: float,
    total_trades: int,
) -> Stability:
    if total_trades < 5 or max_drawdown > 0.35:
        risk_level = "critical"
        score = max(0.0, min(0.3, win_rate * 0.5))
    elif max_drawdown > 0.20 or win_rate < 0.40 or profit_factor < 1.0:
        risk_level = "high"
        score = max(0.3, min(0.55, win_rate * 0.7))
    elif max_drawdown > 0.10 or win_rate < 0.55 or profit_factor < 1.5:
        risk_level = "medium"
        score = max(0.55, min(0.75, win_rate * 0.9))
    else:
        risk_level = "low"
        score = max(0.75, min(1.0, win_rate * 1.1))

    return Stability(
        score=score,
        risk_level=risk_level,
        metrics={
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
            "net_profit": net_profit,
            "total_trades": total_trades,
        },
    )


def _validate_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _require_dict(raw: Any, kind: str) -> None:
    if not isinstance(raw, dict):
        raise ValueError(f"{kind} result must be a dict, or None")


def _require_field(raw: dict, field: str, kind: str) -> Any:
    if field not in raw:
        raise ValueError(f"{kind} record is missing required field '{field}'")
    return raw[field]

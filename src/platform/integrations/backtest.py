"""Read-only integration port for external backtest execution engines.

The original AI-Trading-Lab repository is an external research/engine source.
Backtest engines execute outside this platform. This port lets the platform
consume an external backtest honestly: the engine receives a strategy name, symbol,
timeframe, candles, and initial parameters, and returns an optional raw
backtest result dict. Returning ``None`` means the backtest engine genuinely
cannot produce a backtest for the context; it is never invented here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Sequence

from src.platform.domain.market import Candle


class BacktestSource(ABC):
    """External backtest engine port that emits raw backtest performance records."""

    @abstractmethod
    def run_backtest(
        self,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        candles: Sequence[Candle],
        initial_capital: float = 10000.0,
    ) -> Optional[Dict[str, Any]]:
        """Return a raw backtest result dict, or None when backtest is unavailable."""
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> Dict[str, Any]:
        """Return a small serializable description of the backtest source."""
        raise NotImplementedError

"""Unavailable AI-Trading-Lab source.

Explicit placeholder that never fabricates engine artifacts. Use this until
a real read-only adapter is wired to exported Lab outputs.
"""

from typing import Any, Dict, Optional

from .lab import LabArtifactSource


class UnavailableLabArtifactSource(LabArtifactSource):
    """Read-only source that reports all Lab artifacts as unavailable."""

    def connect(self) -> None:
        return None

    def fetch_signal(self, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        self._validate_symbol(symbol)
        self._validate_timeframe(timeframe)
        return None

    def fetch_trade_setup(self, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        self._validate_symbol(symbol)
        self._validate_timeframe(timeframe)
        return None

    def fetch_stability(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        if not isinstance(strategy_name, str) or strategy_name.strip() == "":
            raise ValueError("strategy_name must be a non-empty string")
        return None

    def close(self) -> None:
        return None

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "UnavailableLabArtifactSource",
            "mode": "read-only",
            "available": False,
            "reason": "AI-Trading-Lab artifacts are not connected",
        }

    def _validate_symbol(self, symbol: str) -> None:
        if not isinstance(symbol, str) or symbol.strip() == "":
            raise ValueError("symbol must be a non-empty string")

    def _validate_timeframe(self, timeframe: str) -> None:
        if not isinstance(timeframe, str) or timeframe.strip() == "":
            raise ValueError("timeframe must be a non-empty string")

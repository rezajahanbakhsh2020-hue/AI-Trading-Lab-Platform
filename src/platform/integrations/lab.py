"""Read-only integration port for AI-Trading-Lab artifacts.

The original AI-Trading-Lab repository is an external research/engine source.
This platform may consume selected outputs only through this port.

Implementations MUST:
- treat the original project as read-only
- never write, commit, or otherwise mutate that repository
- never import its internal implementation modules
- never fabricate signals, trade setups, stability scores, or prices
- report missing data as unavailable (None) rather than inventing values
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class LabArtifactSource(ABC):
    """Port for read-only AI-Trading-Lab artifact access."""

    @abstractmethod
    def connect(self) -> None:
        """Prepare any required resources for read-only access."""
        raise NotImplementedError

    @abstractmethod
    def fetch_signal(self, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        """Return a raw signal dict, or None when unavailable."""
        raise NotImplementedError

    @abstractmethod
    def fetch_trade_setup(self, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        """Return a raw trade-setup dict, or None when unavailable."""
        raise NotImplementedError

    @abstractmethod
    def fetch_stability(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """Return a raw stability dict, or None when unavailable."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Cleanly release any resources."""
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> Dict[str, Any]:
        """Return a small serializable description of the source."""
        raise NotImplementedError

"""Read-only integration port for Project 1 (AI-Trading-Lab) signal emission.

The platform (Project 2) acts as host, presentation, and delivery shell.
Project 1 remains the strategy and decision engine. This port allows Project 2
to fetch or receive signals produced by Project 1 without mutating or coupling
to Project 1 internals.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.platform.domain.presented_signal import PresentedSignal


class Project1IntegrationPort(ABC):
    """Abstract port for receiving/fetching real trading signals from Project 1."""

    @abstractmethod
    def fetch_latest_signal(
        self,
        symbol: str,
        timeframe: str,
        strategy_name: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[PresentedSignal]:
        """Fetch latest presented signal produced by Project 1, or None if unavailable."""
        raise NotImplementedError

    @abstractmethod
    def describe(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Return description of Project 1 integration source status."""
        raise NotImplementedError

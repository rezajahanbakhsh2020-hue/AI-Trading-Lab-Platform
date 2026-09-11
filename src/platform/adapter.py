from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class Adapter(ABC):
    """Abstract base class for platform adapters.

    Adapters provide a clear integration boundary to external systems
    (market data providers, the original AI-Trading-Lab engine, storage, etc.).

    Implementations must avoid modifying the original AI-Trading-Lab repository
    and must operate through well-defined interfaces.
    """

    @abstractmethod
    def connect(self) -> None:
        """Prepare any required connections or resources."""
        raise NotImplementedError

    @abstractmethod
    def fetch_market_data(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch historical market data (candles) for a given symbol and timeframe.

        Return value must be a list of dictionaries where each dictionary contains at minimum:
          - 'timestamp' : an integer or ISO timestamp identifying the candle
          - 'open'      : float
          - 'high'      : float
          - 'low'       : float
          - 'close'     : float
        Optional fields may include:
          - 'volume'    : float (may be absent when the data source does not provide volume)

        Adapters MUST NOT fabricate data. If real data is unavailable, adapters should raise a clear exception.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Cleanly close any connections or resources."""
        raise NotImplementedError

    def describe(self) -> Dict[str, Any]:
        """Optional description of the adapter (name, capabilities)."""
        return {"name": self.__class__.__name__}

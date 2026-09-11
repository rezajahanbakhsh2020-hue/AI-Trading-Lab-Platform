from abc import ABC, abstractmethod
from typing import Any, Dict, List


class MarketDataProvider(ABC):
    """Provider-side port for raw market data.

    This abstract base class defines the provider contract (PORT) that
    upstream concrete market data providers should implement. It is
    intentionally separate from the platform Adapter abstraction and does
    NOT depend on platform Adapter types.

    Provider contract (summary):
    - fetch_candles must return a list of plain dictionaries. Each dict
      MUST contain the required keys: 'timestamp', 'open', 'high', 'low', 'close'.
    - 'volume' is optional and may be omitted when not available.
    - Returned candle lists SHOULD be oldest-first (chronological). Concrete
      providers that receive newest-first upstream data MUST normalize order
      at the provider boundary without fabricating, dropping, or inventing bars.
    - Network access MUST be explicit. Construction, import, and describe()
      MUST NOT perform I/O. connect()/close() control lifecycle; close() is
      idempotent; fetch after close MUST fail rather than silently reopen.
    - Providers MUST NOT fabricate missing market-data fields or silently
      repair malformed values. Validation and conversion into domain
      Candle objects is the responsibility of the application/service
      layer (MarketDataService).
    - Providers MUST NOT perform network access at the port definition
      level or require API keys in this abstraction. Concrete provider
      implementations may perform network requests, but the port itself
      is a simple contract with no external dependencies.
    - The provider MUST return raw data (dicts) and MUST NOT convert
      records into domain Candle objects.
    """

    @abstractmethod
    def connect(self) -> None:
        """Prepare any required resources or connections.

        Implementations may be no-ops. Implementations should raise on
        fatal setup errors.
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch raw candle records for the requested instrument and timeframe.

        Parameters
        - symbol: instrument identifier (non-empty string)
        - timeframe: timeframe string (non-empty string)
        - limit: maximum number of candles to return (int > 0)

        Returns
        - List of dictionaries where each dictionary contains at minimum:
          'timestamp', 'open', 'high', 'low', 'close'. 'volume' is optional.

        Providers MUST NOT fabricate missing fields or silently repair
        malformed data. The service layer is responsible for validation and
        conversion to domain objects.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Cleanly release any resources or connections."""
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> Dict[str, Any]:
        """Return a small serializable description of the provider (name, capabilities)."""
        raise NotImplementedError

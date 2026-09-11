from abc import ABC, abstractmethod
from typing import Any, Dict


class QuoteProvider(ABC):
    """Provider-side port for a single-symbol market quote.

    This port is separate from MarketDataProvider (candles) and from the
    platform Adapter abstraction. Concrete providers return raw dictionaries
    and MUST NOT convert records into domain Quote objects.

    Quote contract (summary):
    - fetch_quote must return a plain dictionary.
    - Required keys: 'symbol', 'timestamp'.
    - At least one price key should be present when the upstream source
      actually supplied it: 'bid', 'ask', 'mid', and/or 'last'.
    - Optional keys: 'change_percent', 'high', 'low', 'availability'.
    - 'availability', when present, is a raw dict with 'status' and optional
      'timestamp', 'age_seconds', and 'reason'.
    - Providers MUST NOT fabricate missing price fields or silently repair
      malformed values. Conversion into domain Quote objects is the
      responsibility of QuoteService.
    """

    @abstractmethod
    def connect(self) -> None:
        """Prepare any required resources or connections."""
        raise NotImplementedError

    @abstractmethod
    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        """Fetch a raw quote record for the requested instrument."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Cleanly release any resources or connections."""
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> Dict[str, Any]:
        """Return a small serializable description of the provider."""
        raise NotImplementedError

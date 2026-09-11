from typing import Any, Dict, List

from src.platform.adapter import Adapter
from src.platform.providers.market_data import MarketDataProvider


class ProviderAdapter(Adapter):
    """Adapter that wraps a MarketDataProvider and exposes the Adapter API.

    The adapter delegates calls to the underlying provider without modifying
    or fabricating market data. This keeps the provider port separate from
    the platform Adapter contract while allowing MarketDataService to use a
    provider via the Adapter interface.
    """

    def __init__(self, provider: MarketDataProvider) -> None:
        if provider is None:
            raise ValueError("provider is required")
        self._provider = provider

    def connect(self) -> None:
        return self._provider.connect()

    def fetch_market_data(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        # Delegate directly to the provider's fetch_candles and return the raw records unchanged.
        return self._provider.fetch_candles(symbol=symbol, timeframe=timeframe, limit=limit)

    def close(self) -> None:
        return self._provider.close()

    def describe(self) -> Dict[str, Any]:
        return self._provider.describe()

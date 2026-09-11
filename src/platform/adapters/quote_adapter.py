from typing import Any, Dict

from src.platform.providers.quote import QuoteProvider


class QuoteAdapter:
    """Adapter that wraps a QuoteProvider without altering quote payloads.

    This adapter is distinct from ProviderAdapter (candles). It exists so
    application services can consume quotes through a stable boundary while
    concrete QuoteProvider implementations remain replaceable.
    """

    def __init__(self, provider: QuoteProvider) -> None:
        if provider is None:
            raise ValueError("provider is required")
        self._provider = provider

    def connect(self) -> None:
        return self._provider.connect()

    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        return self._provider.fetch_quote(symbol=symbol)

    def close(self) -> None:
        return self._provider.close()

    def describe(self) -> Dict[str, Any]:
        return self._provider.describe()

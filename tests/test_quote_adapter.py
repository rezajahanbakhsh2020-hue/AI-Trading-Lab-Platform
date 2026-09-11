import pytest
from typing import Any, Dict

from src.platform.adapters import QuoteAdapter
from src.platform.providers import QuoteProvider


class FakeQuoteProvider(QuoteProvider):
    def __init__(self, data: Dict[str, Any] = None, to_raise: Exception = None):
        self._data = dict(data) if data is not None else {}
        self._to_raise = to_raise
        self.connected = False
        self.closed = False
        self.last_symbol = None

    def connect(self) -> None:
        self.connected = True

    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        self.last_symbol = symbol
        if self._to_raise:
            raise self._to_raise
        return dict(self._data)

    def close(self) -> None:
        self.closed = True

    def describe(self) -> Dict[str, Any]:
        return {"name": "FakeQuoteProvider"}


def test_quote_adapter_importable():
    assert QuoteAdapter is not None


def test_connect_and_close_delegate():
    provider = FakeQuoteProvider({})
    adapter = QuoteAdapter(provider)
    adapter.connect()
    assert provider.connected
    adapter.close()
    assert provider.closed


def test_fetch_delegates_and_preserves_record():
    data = {"symbol": "XAUUSD", "timestamp": "t1", "mid": 4337.7, "bid": 4337.6}
    provider = FakeQuoteProvider(data)
    adapter = QuoteAdapter(provider)
    out = adapter.fetch_quote("XAUUSD")
    assert provider.last_symbol == "XAUUSD"
    assert out == data
    assert "ask" not in out
    assert adapter.describe()["name"] == "FakeQuoteProvider"


def test_provider_exceptions_propagate():
    provider = FakeQuoteProvider(to_raise=RuntimeError("quote error"))
    adapter = QuoteAdapter(provider)
    with pytest.raises(RuntimeError):
        adapter.fetch_quote("XAUUSD")


def test_none_provider_rejected():
    with pytest.raises(ValueError):
        QuoteAdapter(None)  # type: ignore[arg-type]

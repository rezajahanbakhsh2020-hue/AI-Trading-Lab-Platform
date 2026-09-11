import pytest
from typing import Any, Dict

from src.platform.providers import QuoteProvider


def test_quote_provider_importable_and_abstract():
    assert QuoteProvider is not None
    with pytest.raises(TypeError):
        QuoteProvider()  # type: ignore


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


def test_fake_provider_lifecycle_and_fetch():
    data = {"symbol": "XAUUSD", "timestamp": "t1", "mid": 1.0}
    provider = FakeQuoteProvider(data)
    provider.connect()
    assert provider.connected
    out = provider.fetch_quote("XAUUSD")
    assert out == data
    assert isinstance(out, dict)
    assert provider.last_symbol == "XAUUSD"
    assert provider.describe()["name"] == "FakeQuoteProvider"
    provider.close()
    assert provider.closed


def test_provider_exceptions_propagate():
    provider = FakeQuoteProvider(to_raise=RuntimeError("quote failure"))
    with pytest.raises(RuntimeError):
        provider.fetch_quote("XAUUSD")


def test_provider_does_not_convert_to_domain_objects():
    from src.platform.domain.quote import Quote

    provider = FakeQuoteProvider({"symbol": "EURUSD", "timestamp": 1, "bid": 1.1})
    out = provider.fetch_quote("EURUSD")
    assert isinstance(out, dict)
    assert not isinstance(out, Quote)

import pytest

from src.platform.adapters.quote_adapter import QuoteAdapter
from src.platform.domain.quote import Quote
from src.platform.providers.quote import QuoteProvider
from src.platform.services import QuoteService


class FakeQuoteProvider(QuoteProvider):
    def __init__(self, data=None, to_raise=None):
        self.to_return = data if data is not None else {}
        self.to_raise = to_raise
        self.last_symbol = None

    def connect(self) -> None:
        pass

    def fetch_quote(self, symbol: str):
        self.last_symbol = symbol
        if self.to_raise:
            raise self.to_raise
        return self.to_return

    def close(self) -> None:
        pass

    def describe(self):
        return {"name": "FakeQuoteProvider"}


def _service(data=None, to_raise=None):
    provider = FakeQuoteProvider(data=data, to_raise=to_raise)
    return QuoteService(QuoteAdapter(provider)), provider


def test_valid_quote_becomes_domain_object():
    rec = {
        "symbol": "XAUUSD",
        "timestamp": "2026-09-11T10:00:00Z",
        "bid": 4337.6,
        "ask": 4337.8,
        "mid": 4337.7,
        "change_percent": -0.09,
        "high": 4350.0,
        "low": 4330.0,
        "availability": {"status": "live", "age_seconds": 0},
    }
    svc, _ = _service(rec)
    quote = svc.get_quote("XAUUSD")
    assert isinstance(quote, Quote)
    assert quote.symbol == "XAUUSD"
    assert quote.timestamp == rec["timestamp"]
    assert quote.bid == 4337.6
    assert quote.ask == 4337.8
    assert quote.mid == 4337.7
    assert quote.change_percent == -0.09
    assert quote.availability.status == "live"
    assert quote.availability.age_seconds == 0.0


def test_missing_optional_prices_remain_none():
    rec = {"symbol": "EURUSD", "timestamp": 1, "mid": 1.08}
    svc, _ = _service(rec)
    quote = svc.get_quote("EURUSD")
    assert quote.bid is None
    assert quote.ask is None
    assert quote.last is None
    assert quote.availability is None


def test_zero_last_preserved():
    rec = {"symbol": "EURUSD", "timestamp": 1, "last": 0, "mid": 1.08}
    svc, _ = _service(rec)
    quote = svc.get_quote("EURUSD")
    assert quote.last == 0.0


@pytest.mark.parametrize("symbol", [123, "", "   "])
def test_invalid_symbol_raises(symbol):
    svc, _ = _service({"symbol": "XAUUSD", "timestamp": 1, "mid": 1})
    with pytest.raises(ValueError):
        svc.get_quote(symbol)  # type: ignore[arg-type]


def test_missing_required_field_raises():
    svc, _ = _service({"symbol": "XAUUSD", "mid": 1.0})
    with pytest.raises(ValueError):
        svc.get_quote("XAUUSD")


def test_non_dict_payload_raises():
    svc, _ = _service(["not-a-dict"])
    with pytest.raises(ValueError):
        svc.get_quote("XAUUSD")


def test_provider_exception_propagates():
    svc, _ = _service(to_raise=RuntimeError("adapter failure"))
    with pytest.raises(RuntimeError):
        svc.get_quote("XAUUSD")


def test_adapter_receives_exact_symbol():
    rec = {"symbol": "MY-SYM", "timestamp": 1, "mid": 1}
    svc, provider = _service(rec)
    svc.get_quote("MY-SYM")
    assert provider.last_symbol == "MY-SYM"


def test_invalid_availability_shape_raises():
    rec = {"symbol": "EURUSD", "timestamp": 1, "mid": 1, "availability": "live"}
    svc, _ = _service(rec)
    with pytest.raises(ValueError):
        svc.get_quote("EURUSD")

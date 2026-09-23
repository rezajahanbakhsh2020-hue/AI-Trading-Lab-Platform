import json
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest

from src.platform.adapters import QuoteAdapter
from src.platform.domain.quote import Quote
from src.platform.providers import BiQuoteQuoteProvider, QuoteProvider
from src.platform.services import QuoteService


def _tick(**overrides):
    payload = {
        "symbol": "XAUUSD",
        "description": "Gold vs US Dollar",
        "bid": 4337.6,
        "ask": 4337.8,
        "mid": 4337.7,
        "spread": 0.2,
        "last": 4337.7,
        "volume": 0,
        "high": 4350.0,
        "low": 4330.0,
        "direction": "DOWN",
        "dayDiffPercent": -0.09,
        "timestamp": "2026-09-11T10:30:00Z",
        "time": "2026.09.11 10:30:00",
        "source": "MetaTrader 5 (Broker 1)",
        "marketState": "open",
        "stale": False,
        "quoteAgeSeconds": 0,
        "lastQuoteAt": "2026-09-11T10:30:00Z",
    }
    payload.update(overrides)
    return payload


class FakeHTTPResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self, amt: int = None) -> bytes:
        if amt is None:
            return self._body
        return self._body[:amt]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def _json_bytes(payload) -> bytes:
    return json.dumps(payload).encode("utf-8")


def test_implements_quote_provider():
    assert issubclass(BiQuoteQuoteProvider, QuoteProvider)
    assert isinstance(BiQuoteQuoteProvider(), QuoteProvider)


def test_lifecycle_connect_close_describe():
    provider = BiQuoteQuoteProvider(base_url="https://biquote.io")
    provider.connect()
    desc = provider.describe()
    assert desc["name"] == "BiQuoteQuoteProvider"
    assert desc["provider"] == "biquote"
    assert desc["endpoint"] == "tick"
    provider.close()


@patch("src.platform.providers.biquote_quote.urllib.request.urlopen")
def test_fetch_normalizes_tick_fields(mock_urlopen):
    mock_urlopen.return_value = FakeHTTPResponse(_json_bytes(_tick()))
    out = BiQuoteQuoteProvider().fetch_quote("XAUUSD")
    assert isinstance(out, dict)
    assert not isinstance(out, Quote)
    assert out["symbol"] == "XAUUSD"
    assert out["timestamp"] == "2026-09-11T10:30:00Z"
    assert out["bid"] == 4337.6
    assert out["ask"] == 4337.8
    assert out["mid"] == 4337.7
    assert out["last"] == 4337.7
    assert out["change_percent"] == -0.09
    assert out["high"] == 4350.0
    assert out["low"] == 4330.0
    assert out["availability"]["status"] == "live"
    assert out["availability"]["age_seconds"] == 0
    assert "spread" not in out
    assert "description" not in out
    assert "marketState" not in out
    assert "dayDiffPercent" not in out


@patch("src.platform.providers.biquote_quote.urllib.request.urlopen")
def test_closed_market_maps_to_closed_availability(mock_urlopen):
    mock_urlopen.return_value = FakeHTTPResponse(
        _json_bytes(_tick(marketState="closed", quoteAgeSeconds=3600))
    )
    out = BiQuoteQuoteProvider().fetch_quote("EURUSD")
    assert out["availability"]["status"] == "closed"
    assert out["availability"]["reason"] == "market closed"
    assert out["availability"]["age_seconds"] == 3600


@patch("src.platform.providers.biquote_quote.urllib.request.urlopen")
def test_stale_flag_maps_to_stale_availability(mock_urlopen):
    mock_urlopen.return_value = FakeHTTPResponse(_json_bytes(_tick(stale=True, quoteAgeSeconds=12)))
    out = BiQuoteQuoteProvider().fetch_quote("EURUSD")
    assert out["availability"]["status"] == "stale"
    assert out["availability"]["age_seconds"] == 12


@patch("src.platform.providers.biquote_quote.urllib.request.urlopen")
def test_missing_optional_fields_are_not_fabricated(mock_urlopen):
    payload = {"symbol": "EURUSD", "timestamp": "t1", "mid": 1.08}
    mock_urlopen.return_value = FakeHTTPResponse(_json_bytes(payload))
    out = BiQuoteQuoteProvider().fetch_quote("EURUSD")
    assert "bid" not in out
    assert "ask" not in out
    assert "availability" not in out
    assert out["mid"] == 1.08


@patch("src.platform.providers.biquote_quote.urllib.request.urlopen")
def test_request_url_uses_symbol(mock_urlopen):
    mock_urlopen.return_value = FakeHTTPResponse(_json_bytes(_tick()))
    BiQuoteQuoteProvider(base_url="https://biquote.io").fetch_quote("XAUUSD")
    request = mock_urlopen.call_args.args[0]
    assert request.full_url == "https://biquote.io/api/XAUUSD"
    assert mock_urlopen.call_args.kwargs["timeout"] == 10.0


@pytest.mark.parametrize("bad_symbol", [None, 123, "", "   ", "XAU/USD", "EUR USD"])
def test_invalid_symbol_raises(bad_symbol):
    with pytest.raises(ValueError):
        BiQuoteQuoteProvider().fetch_quote(bad_symbol)  # type: ignore[arg-type]


@patch("src.platform.providers.biquote_quote.urllib.request.urlopen")
def test_http_error_raises_runtime_error(mock_urlopen):
    mock_urlopen.side_effect = HTTPError(
        url="https://biquote.io/api/NOPE",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=BytesIO(b'{"message":"unknown symbol"}'),
    )
    with pytest.raises(RuntimeError, match="BiQuote HTTP 404"):
        BiQuoteQuoteProvider().fetch_quote("NOPE")


@patch("src.platform.providers.biquote_quote.urllib.request.urlopen")
def test_network_error_raises_runtime_error(mock_urlopen):
    mock_urlopen.side_effect = URLError("connection refused")
    with pytest.raises(RuntimeError, match="BiQuote request failed"):
        BiQuoteQuoteProvider().fetch_quote("XAUUSD")


@patch("src.platform.providers.biquote_quote.urllib.request.urlopen")
def test_invalid_json_raises_value_error(mock_urlopen):
    mock_urlopen.return_value = FakeHTTPResponse(b"not-json")
    with pytest.raises(ValueError, match="invalid JSON"):
        BiQuoteQuoteProvider().fetch_quote("XAUUSD")


@patch("src.platform.providers.biquote_quote.urllib.request.urlopen")
def test_works_through_adapter_and_service(mock_urlopen):
    mock_urlopen.return_value = FakeHTTPResponse(_json_bytes(_tick()))
    provider = BiQuoteQuoteProvider()
    service = QuoteService(QuoteAdapter(provider))
    quote = service.get_quote("XAUUSD")
    assert isinstance(quote, Quote)
    assert quote.symbol == "XAUUSD"
    assert quote.mid == 4337.7
    assert quote.availability.status == "live"


def test_invalid_constructor_arguments():
    with pytest.raises(ValueError):
        BiQuoteQuoteProvider(base_url="")
    with pytest.raises(ValueError):
        BiQuoteQuoteProvider(timeout=0)


@patch("src.platform.providers.biquote_quote.urllib.request.urlopen")
def test_construction_and_describe_do_not_network(mock_urlopen):
    provider = BiQuoteQuoteProvider()
    provider.describe()
    mock_urlopen.assert_not_called()


@patch("src.platform.providers.biquote_quote.urllib.request.urlopen")
def test_fetch_after_close_raises_until_reconnect(mock_urlopen):
    mock_urlopen.return_value = FakeHTTPResponse(_json_bytes(_tick()))
    provider = BiQuoteQuoteProvider()
    provider.close()
    with pytest.raises(RuntimeError, match="closed"):
        provider.fetch_quote("XAUUSD")
    mock_urlopen.assert_not_called()
    provider.connect()
    out = provider.fetch_quote("XAUUSD")
    assert out["symbol"] == "XAUUSD"

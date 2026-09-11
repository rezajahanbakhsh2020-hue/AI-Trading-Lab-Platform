import json
from io import BytesIO
from typing import Any, Dict, List
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest

from src.platform.adapters import ProviderAdapter
from src.platform.domain.market import Candle
from src.platform.providers import BiQuoteProvider, MarketDataProvider
from src.platform.providers.biquote import SUPPORTED_INTERVALS
from src.platform.services import MarketDataService


def _payload(bars: List[Dict[str, Any]], symbol: str = "XAUUSD", interval: str = "1h") -> Dict[str, Any]:
    return {"symbol": symbol, "interval": interval, "bars": bars}


def _newest_first_bars() -> List[Dict[str, Any]]:
    return [
        {
            "openTime": "2026-09-11T11:00:00Z",
            "open": 4337.7,
            "high": 4342.723,
            "low": 4335.841,
            "close": 4336.368,
            "volume": 0,
            "tickVolume": 1254,
            "isOpen": True,
        },
        {
            "openTime": "2026-09-11T10:00:00Z",
            "open": 4346.644,
            "high": 4350.141,
            "low": 4336.68,
            "close": 4337.838,
            "volume": 12.5,
            "tickVolume": 6641,
            "isOpen": False,
        },
        {
            "openTime": "2026-09-11T09:00:00Z",
            "open": 4347.434,
            "high": 4354.129,
            "low": 4340.848,
            "close": 4346.337,
            "volume": 8,
            "tickVolume": 6588,
            "isOpen": False,
        },
    ]


class FakeHTTPResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload).encode("utf-8")


def test_biquote_provider_importable_and_implements_port():
    assert BiQuoteProvider is not None
    assert issubclass(BiQuoteProvider, MarketDataProvider)
    provider = BiQuoteProvider()
    assert isinstance(provider, MarketDataProvider)


def test_lifecycle_connect_close_describe():
    provider = BiQuoteProvider(base_url="https://biquote.io")
    provider.connect()
    desc = provider.describe()
    assert isinstance(desc, dict)
    assert desc["name"] == "BiQuoteProvider"
    assert desc["provider"] == "biquote"
    assert desc["base_url"] == "https://biquote.io"
    assert desc["supported_timeframes"] == list(SUPPORTED_INTERVALS)
    provider.close()


@patch("src.platform.providers.biquote.urllib.request.urlopen")
def test_fetch_normalizes_fields_and_reverses_newest_first(mock_urlopen):
    mock_urlopen.return_value = FakeHTTPResponse(_json_bytes(_payload(_newest_first_bars())))
    provider = BiQuoteProvider()
    provider.connect()
    out = provider.fetch_candles("XAUUSD", "1h", limit=3)

    assert len(out) == 3
    assert all(isinstance(item, dict) for item in out)
    assert [item["timestamp"] for item in out] == [
        "2026-09-11T09:00:00Z",
        "2026-09-11T10:00:00Z",
        "2026-09-11T11:00:00Z",
    ]
    assert out[0]["open"] == 4347.434
    assert out[0]["high"] == 4354.129
    assert out[0]["low"] == 4340.848
    assert out[0]["close"] == 4346.337
    assert out[0]["volume"] == 8
    assert out[1]["volume"] == 12.5
    assert out[2]["volume"] == 0
    assert "tickVolume" not in out[0]
    assert "isOpen" not in out[0]
    assert "openTime" not in out[0]


@patch("src.platform.providers.biquote.urllib.request.urlopen")
def test_volume_omitted_when_absent(mock_urlopen):
    bars = [
        {"openTime": "t2", "open": 2, "high": 3, "low": 1, "close": 2.5},
        {"openTime": "t1", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100},
    ]
    mock_urlopen.return_value = FakeHTTPResponse(_json_bytes(_payload(bars)))
    out = BiQuoteProvider().fetch_candles("XAUUSD", "1h", 2)
    assert out[0]["timestamp"] == "t1"
    assert out[0]["volume"] == 100
    assert "volume" not in out[1]


@patch("src.platform.providers.biquote.urllib.request.urlopen")
def test_provider_returns_raw_dicts_not_candles(mock_urlopen):
    bars = [{"openTime": "ts", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 0}]
    mock_urlopen.return_value = FakeHTTPResponse(_json_bytes(_payload(bars)))
    out = BiQuoteProvider().fetch_candles("EURUSD", "1d", 1)
    assert isinstance(out[0], dict)
    assert not isinstance(out[0], Candle)


@patch("src.platform.providers.biquote.urllib.request.urlopen")
def test_request_url_uses_symbol_interval_and_limit(mock_urlopen):
    mock_urlopen.return_value = FakeHTTPResponse(_json_bytes(_payload([])))
    BiQuoteProvider(base_url="https://biquote.io").fetch_candles("XAUUSD", "15m", 50)
    request = mock_urlopen.call_args.args[0]
    assert request.full_url == "https://biquote.io/api/XAUUSD/ohlc?interval=15m&limit=50"
    assert mock_urlopen.call_args.kwargs["timeout"] == 10.0


@patch("src.platform.providers.biquote.urllib.request.urlopen")
def test_limit_trims_to_most_recent_after_ordering(mock_urlopen):
    mock_urlopen.return_value = FakeHTTPResponse(_json_bytes(_payload(_newest_first_bars())))
    out = BiQuoteProvider().fetch_candles("XAUUSD", "1h", 2)
    assert [item["timestamp"] for item in out] == [
        "2026-09-11T10:00:00Z",
        "2026-09-11T11:00:00Z",
    ]


@pytest.mark.parametrize("bad_symbol", [None, 123, "", "   ", "XAU/USD", "EUR USD"])
def test_invalid_symbol_raises(bad_symbol):
    with pytest.raises(ValueError):
        BiQuoteProvider().fetch_candles(bad_symbol, "1h", 1)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_timeframe", [None, 1, "", "   ", "2h", "H1", "1H"])
def test_invalid_timeframe_raises(bad_timeframe):
    with pytest.raises(ValueError):
        BiQuoteProvider().fetch_candles("XAUUSD", bad_timeframe, 1)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_limit", [0, -1, 1001, 1.5, "100", True])
def test_invalid_limit_raises(bad_limit):
    with pytest.raises(ValueError):
        BiQuoteProvider().fetch_candles("XAUUSD", "1h", bad_limit)  # type: ignore[arg-type]


@pytest.mark.parametrize("interval", list(SUPPORTED_INTERVALS))
@patch("src.platform.providers.biquote.urllib.request.urlopen")
def test_supported_intervals_accepted(mock_urlopen, interval):
    mock_urlopen.return_value = FakeHTTPResponse(_json_bytes(_payload([])))
    BiQuoteProvider().fetch_candles("BTCUSD", interval, 1)
    request = mock_urlopen.call_args.args[0]
    assert f"interval={interval}" in request.full_url


@patch("src.platform.providers.biquote.urllib.request.urlopen")
def test_http_error_raises_runtime_error(mock_urlopen):
    mock_urlopen.side_effect = HTTPError(
        url="https://biquote.io/api/NOPE/ohlc",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=BytesIO(b'{"message":"unknown symbol"}'),
    )
    with pytest.raises(RuntimeError, match="BiQuote HTTP 404"):
        BiQuoteProvider().fetch_candles("NOPE", "1h", 1)


@patch("src.platform.providers.biquote.urllib.request.urlopen")
def test_network_error_raises_runtime_error(mock_urlopen):
    mock_urlopen.side_effect = URLError("connection refused")
    with pytest.raises(RuntimeError, match="BiQuote request failed"):
        BiQuoteProvider().fetch_candles("XAUUSD", "1h", 1)


@patch("src.platform.providers.biquote.urllib.request.urlopen")
def test_invalid_json_raises_value_error(mock_urlopen):
    mock_urlopen.return_value = FakeHTTPResponse(b"not-json")
    with pytest.raises(ValueError, match="invalid JSON"):
        BiQuoteProvider().fetch_candles("XAUUSD", "1h", 1)


@patch("src.platform.providers.biquote.urllib.request.urlopen")
def test_missing_bars_raises_value_error(mock_urlopen):
    mock_urlopen.return_value = FakeHTTPResponse(_json_bytes({"symbol": "XAUUSD"}))
    with pytest.raises(ValueError, match="missing 'bars'"):
        BiQuoteProvider().fetch_candles("XAUUSD", "1h", 1)


@patch("src.platform.providers.biquote.urllib.request.urlopen")
def test_non_object_bar_raises_value_error(mock_urlopen):
    mock_urlopen.return_value = FakeHTTPResponse(_json_bytes(_payload(["bad"])))
    with pytest.raises(ValueError, match="bar must be a JSON object"):
        BiQuoteProvider().fetch_candles("XAUUSD", "1h", 1)


@patch("src.platform.providers.biquote.urllib.request.urlopen")
def test_does_not_fabricate_missing_ohlc_fields(mock_urlopen):
    bars = [{"openTime": "t1", "open": 1, "high": 1, "close": 1}]
    mock_urlopen.return_value = FakeHTTPResponse(_json_bytes(_payload(bars)))
    out = BiQuoteProvider().fetch_candles("XAUUSD", "1h", 1)
    assert "low" not in out[0]
    assert out[0]["timestamp"] == "t1"


@patch("src.platform.providers.biquote.urllib.request.urlopen")
def test_works_through_provider_adapter_and_service(mock_urlopen):
    mock_urlopen.return_value = FakeHTTPResponse(_json_bytes(_payload(_newest_first_bars())))
    provider = BiQuoteProvider()
    adapter = ProviderAdapter(provider)
    service = MarketDataService(adapter)
    candles = service.get_candles("XAUUSD", "1h", 3)
    assert [c.timestamp for c in candles] == [
        "2026-09-11T09:00:00Z",
        "2026-09-11T10:00:00Z",
        "2026-09-11T11:00:00Z",
    ]
    assert all(isinstance(c, Candle) for c in candles)
    assert candles[1].volume == 12.5


def test_invalid_constructor_arguments():
    with pytest.raises(ValueError):
        BiQuoteProvider(base_url="")
    with pytest.raises(ValueError):
        BiQuoteProvider(timeout=0)
    with pytest.raises(ValueError):
        BiQuoteProvider(timeout=-1)

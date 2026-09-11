"""Concrete BiQuote market-data provider.

Implements the MarketDataProvider port using the public BiQuote REST API.
Returns raw candle dictionaries; domain conversion remains in MarketDataService.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from .http import MAX_RESPONSE_BYTES, read_limited
from .market_data import MarketDataProvider

SUPPORTED_INTERVALS = ("1m", "5m", "15m", "30m", "1h", "4h", "1d")
DEFAULT_BASE_URL = "https://biquote.io"
DEFAULT_TIMEOUT_SECONDS = 10.0
MIN_LIMIT = 1
MAX_LIMIT = 1000
USER_AGENT = "AI-Trading-Lab-Platform/0.1.0"


class BiQuoteProvider(MarketDataProvider):
    """MarketDataProvider backed by BiQuote public OHLC REST endpoint."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not isinstance(base_url, str) or base_url.strip() == "":
            raise ValueError("base_url must be a non-empty string")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise ValueError("timeout must be a number")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        self._base_url = base_url.rstrip("/")
        self._timeout = float(timeout)
        self._connected = False
        self._closed = False

    def connect(self) -> None:
        """Mark the provider ready. Does not open a network connection."""
        self._connected = True
        self._closed = False

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        if self._closed:
            raise RuntimeError("BiQuoteProvider is closed")
        normalized_symbol = self._validate_symbol(symbol)
        normalized_timeframe = self._validate_timeframe(timeframe)
        normalized_limit = self._validate_limit(limit)

        url = self._build_url(normalized_symbol, normalized_timeframe, normalized_limit)
        payload = self._get_json(url)
        bars = self._extract_bars(payload)
        records = [self._normalize_bar(bar) for bar in bars]
        chronological = self._oldest_first(records)
        if len(chronological) > normalized_limit:
            chronological = chronological[-normalized_limit:]
        return chronological

    def close(self) -> None:
        """Idempotent close. Subsequent fetches fail until connect()."""
        self._connected = False
        self._closed = True

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "BiQuoteProvider",
            "provider": "biquote",
            "base_url": self._base_url,
            "supported_timeframes": list(SUPPORTED_INTERVALS),
            "min_limit": MIN_LIMIT,
            "max_limit": MAX_LIMIT,
            "candle_order": "oldest-first",
        }

    def _validate_symbol(self, symbol: str) -> str:
        if not isinstance(symbol, str):
            raise ValueError("symbol must be a string")
        normalized = symbol.strip()
        if normalized == "":
            raise ValueError("symbol must not be empty or whitespace")
        if not all(ch.isalnum() or ch in "._-" for ch in normalized):
            raise ValueError("symbol contains unsupported characters")
        return normalized

    def _validate_timeframe(self, timeframe: str) -> str:
        if not isinstance(timeframe, str):
            raise ValueError("timeframe must be a string")
        normalized = timeframe.strip()
        if normalized == "":
            raise ValueError("timeframe must not be empty or whitespace")
        if normalized not in SUPPORTED_INTERVALS:
            raise ValueError(
                "timeframe must be one of: " + ", ".join(SUPPORTED_INTERVALS)
            )
        return normalized

    def _validate_limit(self, limit: int) -> int:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit must be an integer")
        if limit < MIN_LIMIT or limit > MAX_LIMIT:
            raise ValueError(
                f"limit must be between {MIN_LIMIT} and {MAX_LIMIT} inclusive"
            )
        return limit

    def _build_url(self, symbol: str, timeframe: str, limit: int) -> str:
        path = "/api/" + urllib.parse.quote(symbol, safe="") + "/ohlc"
        query = urllib.parse.urlencode({"interval": timeframe, "limit": limit})
        return self._base_url + path + "?" + query

    def _get_json(self, url: str) -> Any:
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = read_limited(response)
        except urllib.error.HTTPError as exc:
            try:
                detail = read_limited(exc, max_bytes=min(4096, MAX_RESPONSE_BYTES))
                text = detail.decode("utf-8", errors="replace")
            except Exception:
                text = ""
            raise RuntimeError(
                f"BiQuote HTTP {exc.code} while fetching candles: {text}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"BiQuote request failed while fetching candles: {exc.reason}"
            ) from exc
        except TimeoutError as exc:
            raise RuntimeError("BiQuote request timed out while fetching candles") from exc

        if not body:
            raise ValueError("BiQuote returned an empty response body")

        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("BiQuote returned invalid JSON") from exc

    def _extract_bars(self, payload: Any) -> List[Any]:
        if not isinstance(payload, dict):
            raise ValueError("BiQuote OHLC response must be a JSON object")
        if "bars" not in payload:
            raise ValueError("BiQuote OHLC response is missing 'bars'")
        bars = payload["bars"]
        if not isinstance(bars, list):
            raise ValueError("BiQuote OHLC 'bars' must be a list")
        return bars

    def _normalize_bar(self, bar: Any) -> Dict[str, Any]:
        if not isinstance(bar, dict):
            raise ValueError("BiQuote bar must be a JSON object")

        record: Dict[str, Any] = {}
        if "openTime" in bar:
            record["timestamp"] = bar["openTime"]
        for field in ("open", "high", "low", "close"):
            if field in bar:
                record[field] = bar[field]
        if "volume" in bar:
            record["volume"] = bar["volume"]
        return record

    def _oldest_first(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return chronological candles without fabricating or dropping bars.

        BiQuote documents newest-first bars. If timestamps show newest-first,
        reverse once. If already oldest-first, or timestamps cannot be compared,
        keep the original sequence.
        """
        if len(records) < 2:
            return records
        first = records[0].get("timestamp")
        last = records[-1].get("timestamp")
        if first is None or last is None:
            return records
        try:
            if last < first:
                return list(reversed(records))
        except TypeError:
            return records
        return records

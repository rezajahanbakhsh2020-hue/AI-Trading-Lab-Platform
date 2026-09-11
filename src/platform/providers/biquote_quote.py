"""Concrete BiQuote quote provider.

Implements QuoteProvider using the public BiQuote REST tick endpoint.
Returns raw quote dictionaries; domain conversion remains in QuoteService.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict

from .quote import QuoteProvider

DEFAULT_BASE_URL = "https://biquote.io"
DEFAULT_TIMEOUT_SECONDS = 10.0
USER_AGENT = "AI-Trading-Lab-Platform/0.1.0"


class BiQuoteQuoteProvider(QuoteProvider):
    """QuoteProvider backed by BiQuote public tick REST endpoint."""

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
        self._connected = True
        self._closed = False

    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        normalized_symbol = self._validate_symbol(symbol)
        url = self._build_url(normalized_symbol)
        payload = self._get_json(url)
        return self._normalize_tick(payload)

    def close(self) -> None:
        self._connected = False
        self._closed = True

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "BiQuoteQuoteProvider",
            "provider": "biquote",
            "base_url": self._base_url,
            "endpoint": "tick",
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

    def _build_url(self, symbol: str) -> str:
        return self._base_url + "/api/" + urllib.parse.quote(symbol, safe="")

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
                body = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"BiQuote HTTP {exc.code} while fetching quote: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"BiQuote request failed while fetching quote: {exc.reason}"
            ) from exc
        except TimeoutError as exc:
            raise RuntimeError("BiQuote request timed out while fetching quote") from exc

        if not body:
            raise ValueError("BiQuote returned an empty response body")

        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("BiQuote returned invalid JSON") from exc

    def _normalize_tick(self, payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("BiQuote tick response must be a JSON object")

        record: Dict[str, Any] = {}
        if "symbol" in payload:
            record["symbol"] = payload["symbol"]
        if "timestamp" in payload:
            record["timestamp"] = payload["timestamp"]

        for source, dest in (
            ("bid", "bid"),
            ("ask", "ask"),
            ("mid", "mid"),
            ("last", "last"),
            ("dayDiffPercent", "change_percent"),
            ("high", "high"),
            ("low", "low"),
        ):
            if source in payload:
                record[dest] = payload[source]

        availability = self._availability_from_payload(payload)
        if availability is not None:
            record["availability"] = availability
        return record

    def _availability_from_payload(self, payload: Dict[str, Any]) -> Dict[str, Any] | None:
        market_state = payload.get("marketState")
        stale = payload.get("stale")
        quote_age = payload.get("quoteAgeSeconds")
        timestamp = payload.get("timestamp")

        status = None
        reason = None
        if stale is True:
            status = "stale"
            reason = "quote marked stale by provider"
        elif isinstance(market_state, str):
            state = market_state.strip().lower()
            if state == "open":
                status = "live"
            elif state == "closed":
                status = "closed"
                reason = "market closed"
            elif state in ("offline", "unavailable"):
                status = state
                reason = "market " + state

        if status is None:
            return None

        availability: Dict[str, Any] = {"status": status}
        if timestamp is not None:
            availability["timestamp"] = timestamp
        if quote_age is not None:
            availability["age_seconds"] = quote_age
        if reason is not None:
            availability["reason"] = reason
        return availability

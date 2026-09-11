"""Quote application service.

Validates inputs, fetches a raw quote through QuoteAdapter, and converts
the record into a Quote domain object. Does not fabricate missing prices.
"""

from typing import Any, Dict, Optional

from src.platform.adapters.quote_adapter import QuoteAdapter
from src.platform.domain.availability import Availability
from src.platform.domain.quote import Quote


class QuoteService:
    """Application service for fetching a single-symbol quote."""

    def __init__(self, adapter: QuoteAdapter) -> None:
        if adapter is None:
            raise ValueError("adapter is required")
        self._adapter = adapter

    def get_quote(self, symbol: str) -> Quote:
        if not isinstance(symbol, str):
            raise ValueError("symbol must be a string")
        if symbol.strip() == "":
            raise ValueError("symbol must not be empty or whitespace")

        raw = self._adapter.fetch_quote(symbol=symbol)
        if not isinstance(raw, dict):
            raise ValueError("adapter.fetch_quote must return a dict quote record")

        required = ("symbol", "timestamp")
        for field in required:
            if field not in raw:
                raise ValueError(f"quote record is missing required field '{field}'")

        availability = self._availability_from_raw(raw.get("availability"))

        return Quote(
            symbol=raw["symbol"],
            timestamp=raw["timestamp"],
            bid=raw.get("bid"),
            ask=raw.get("ask"),
            mid=raw.get("mid"),
            last=raw.get("last"),
            change_percent=raw.get("change_percent"),
            high=raw.get("high"),
            low=raw.get("low"),
            availability=availability,
        )

    def _availability_from_raw(self, raw: Any) -> Optional[Availability]:
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise ValueError("availability must be a dict if provided")
        if "status" not in raw:
            raise ValueError("availability is missing required field 'status'")
        return Availability(
            status=raw["status"],
            timestamp=raw.get("timestamp"),
            age_seconds=raw.get("age_seconds"),
            reason=raw.get("reason"),
        )

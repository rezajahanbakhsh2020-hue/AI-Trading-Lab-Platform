"""Market data application service

Provides MarketDataService which orchestrates adapter fetches and converts
adapter records into Candle domain objects while performing input and data
validation according to Phase 3 requirements.
"""
from typing import Iterable, List

from src.platform.adapter import Adapter
from src.platform.domain.market import Candle

MAX_CANDLES = 10000


class MarketDataService:
    """Application service for fetching market candles through an Adapter.

    Responsibilities:
    - validate service inputs (symbol, timeframe, limit)
    - call the adapter.fetch_market_data(...) method
    - validate adapter output shape
    - translate adapter records into Candle domain objects
    - preserve order and actual values
    """

    def __init__(self, adapter: Adapter) -> None:
        if adapter is None:
            raise ValueError("adapter is required")
        self._adapter = adapter

    def get_candles(self, symbol: str, timeframe: str, limit: int = 100) -> List[Candle]:
        # Input validation
        if not isinstance(symbol, str):
            raise ValueError("symbol must be a string")
        if symbol.strip() == "":
            raise ValueError("symbol must not be empty or whitespace")

        if not isinstance(timeframe, str):
            raise ValueError("timeframe must be a string")
        if timeframe.strip() == "":
            raise ValueError("timeframe must not be empty or whitespace")

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit must be an integer")
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if limit > MAX_CANDLES:
            raise ValueError(f"limit must be at most {MAX_CANDLES}")

        # Fetch data from adapter. Let adapter exceptions propagate.
        raw = self._adapter.fetch_market_data(symbol=symbol, timeframe=timeframe, limit=limit)

        # Validate adapter return type
        if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes)):
            raise ValueError("adapter.fetch_market_data must return an iterable of candle records")

        candles: List[Candle] = []
        required_fields = ("timestamp", "open", "high", "low", "close")

        for idx, rec in enumerate(raw):
            if idx >= MAX_CANDLES:
                raise ValueError("adapter returned too many candle records")
            if not isinstance(rec, dict):
                raise ValueError(f"adapter returned a non-dict candle record at index {idx}")

            for field in required_fields:
                if field not in rec:
                    raise ValueError(f"adapter candle record at index {idx} is missing required field '{field}'")

            # Preserve volume presence/absence. Use None when genuinely absent.
            volume = rec.get("volume", None)

            # Create domain Candle (will validate types/values). Allow exceptions to propagate.
            candle = Candle(
                timestamp=rec["timestamp"],
                open=rec["open"],
                high=rec["high"],
                low=rec["low"],
                close=rec["close"],
                volume=volume,
            )
            candles.append(candle)

        return candles

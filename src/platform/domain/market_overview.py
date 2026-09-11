"""Market overview domain model.

Immutable value object aggregating a snapshot of one instrument: quote,
latest candles,, and optional lab artifacts (signal, trade setup,, stability..
Absent sources remain ``None`` and are never invented..
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from .availability import Availability
from .market import Candle
from .quote import Quote
from .signal import Signal
from .stability import Stability
from .trade_setup import TradeSetup


@dataclass(frozen=True)
class MarketOverview:
    """Immutable market snapshot for one symbol/timeframe."""

    symbol: str
    timeframe: str
    quote: Optional[Quote] = None
    candles: List[Candle] = None  # type: ignore[assignment]
    signal: Optional[Signal] = None
    trade_setup: Optional[TradeSetup] = None
    stability: Optional[Stability] = None
    availability: Optional[Availability] = None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str):
            raise ValueError("symbol must be a string")
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty or whitespace")
        object.__setattr__(self, "symbol", self.symbol.strip())

        if not isinstance(self.timeframe, str):
            raise ValueError("timeframe must be a string")
        if not self.timeframe.strip():
            raise ValueError("timeframe must not be empty or whitespace")
        object.__setattr__(self, "timeframe", self.timeframe.strip())

        if not isinstance(self.candles, list):
            raise ValueError("candles must be a list")
        if not all(isinstance(c, Candle) for c in self.candles):
            raise ValueError("candles must contain only Candle objects")
        object.__setattr__(
            self,
            "candles",
            tuple(c for c in self.candles),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "quote": self.quote.to_dict() if self.quote is not None else None,
            "candles": [c.to_dict() for c in self.candles],
            "signal": self.signal.to_dict() if self.signal is not None else None,
            "trade_setup": self.trade_setup.to_dict() if self.trade_setup is not None else None,
            "stability": self.stability.to_dict() if self.stability is not None else None,
            "availability": self.availability.to_dict() if self.availability is not None else None,
        }

    @property
    def has_quote(self) -> bool:
        return self.quote is not None

    @property
    def has_signal(self) -> bool:
        return self.signal is not None
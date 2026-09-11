"""Platform domain package for market models.

This package contains simple, dependency-light domain models used across the
platform. Presentation/UI code must not live here.
"""

from .availability import Availability
from .instrument import Instrument
from .market import Candle
from .alert import MarketAlert
from .freshness import DataFreshness
from .market_overview import MarketOverview
from .quote import Quote
from .signal import Signal
from .stability import Stability
from .trade_setup import TradeSetup

__all__ = [
    "Availability",
    "MarketAlert",
    "Candle",
    "DataFreshness",
    "Instrument",
    "MarketOverview",
    "Quote",
    "Signal",
    "Stability",
    "TradeSetup",
]

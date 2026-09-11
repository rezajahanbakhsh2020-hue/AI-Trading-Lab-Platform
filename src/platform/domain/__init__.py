"""Platform domain package for market models.

This package contains simple, dependency-light domain models used across the
platform. Presentation/UI code must not live here.
"""

from .availability import Availability
from .instrument import Instrument
from .market import Candle
from .quote import Quote
from .signal import Signal
from .stability import Stability
from .trade_setup import TradeSetup

__all__ = [
    "Availability",
    "Candle",
    "Instrument",
    "Quote",
    "Signal",
    "Stability",
    "TradeSetup",
]

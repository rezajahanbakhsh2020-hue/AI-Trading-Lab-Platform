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
from .provider_readiness import (
    PROVIDER_STATUS_NOT_READY,
    PROVIDER_STATUS_READY,
    VALID_PROVIDER_READINESS_STATUSES,
    ProviderReadiness,
)
from .provider_selection import (
    SELECTION_STATUS_NOT_AVAILABLE,
    SELECTION_STATUS_SELECTED,
    VALID_SELECTION_STATUSES,
    ProviderSelection,
)
from .quote import Quote
from .readiness import Readiness
from .signal import Signal
from .stability import Stability
from .strategy_result import StrategyResult
from .trade_readiness import TradeReadiness
from .trade_setup import TradeSetup
from .trade_signal import TradeSignal

__all__ = [
    "Availability",
    "MarketAlert",
    "Candle",
    "DataFreshness",
    "Instrument",
    "MarketOverview",
    "PROVIDER_STATUS_NOT_READY",
    "PROVIDER_STATUS_READY",
    "VALID_PROVIDER_READINESS_STATUSES",
    "ProviderReadiness",
    "SELECTION_STATUS_NOT_AVAILABLE",
    "SELECTION_STATUS_SELECTED",
    "VALID_SELECTION_STATUSES",
    "ProviderSelection",
    "Quote",
    "Readiness",
    "Signal",
    "Stability",
    "StrategyResult",
    "TradeReadiness",
    "TradeSetup",
    "TradeSignal",
]

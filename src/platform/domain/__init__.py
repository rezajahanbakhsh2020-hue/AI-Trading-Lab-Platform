"""Platform domain package for market models.

This package contains simple, dependency-light domain models used across the
platform. The Candle model lives in src.platform.domain.market and is exposed
from here for convenience.
"""

from .market import Candle

__all__ = ["Candle"]

"""Domain models for Market Screener, Heatmap, and Intelligence Workspace."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class AssetCategory(str, Enum):
    """Categories for multi-asset market filtering."""

    COMMODITIES = "COMMODITIES"
    FOREX = "FOREX"
    CRYPTO = "CRYPTO"
    INDICES = "INDICES"


@dataclass(frozen=True)
class MarketScreenerItem:
    """Represents a single asset in the Market Screener with price, performance, and signal indicators."""

    symbol: str
    display_name: str
    category: AssetCategory
    price: float
    change_24h_percent: float
    volume_24h_usd: float
    volatility_percent: float
    signal_action: Optional[str] = None
    signal_confidence: Optional[float] = None
    extra_metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class HeatmapTile:
    """Represents a visual heatmap tile derived from market screener performance."""

    symbol: str
    display_name: str
    category: AssetCategory
    change_24h_percent: float
    intensity: float  # Normalized 0.0 to 1.0 performance magnitude
    is_positive: bool
    signal_action: Optional[str] = None


@dataclass(frozen=True)
class MarketScreenerFilter:
    """Filter criteria for market screener queries."""

    category: Optional[AssetCategory] = None
    min_volume_usd: Optional[float] = None
    signal_filter: Optional[str] = None  # BUY, SELL, HOLD
    search_query: Optional[str] = None
    sort_by: str = "change_24h_percent"  # change_24h_percent, volume_24h_usd, volatility_percent
    sort_descending: bool = True


@dataclass(frozen=True)
class MarketScreenerResult:
    """Result payload containing screened items, heatmap tiles, and metadata."""

    items: List[MarketScreenerItem]
    heatmap_tiles: List[HeatmapTile]
    total_count: int
    applied_category: Optional[AssetCategory] = None
    applied_search: Optional[str] = None

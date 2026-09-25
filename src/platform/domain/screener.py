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
    price: Optional[float] = None
    change_24h_percent: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    volatility_percent: Optional[float] = None
    signal_action: Optional[str] = None
    signal_confidence: Optional[float] = None
    extra_metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Optional[object]]:
        return {
            "symbol": self.symbol,
            "display_name": self.display_name,
            "category": self.category.value,
            "price": self.price,
            "change_24h_percent": self.change_24h_percent,
            "volume_24h_usd": self.volume_24h_usd,
            "volatility_percent": self.volatility_percent,
            "signal_action": self.signal_action,
            "signal_confidence": self.signal_confidence,
            "extra_metadata": dict(self.extra_metadata),
        }


@dataclass(frozen=True)
class HeatmapTile:
    """Represents a visual heatmap tile derived from market screener performance."""

    symbol: str
    display_name: str
    category: AssetCategory
    change_24h_percent: Optional[float] = None
    intensity: float = 0.0  # Normalized 0.0 to 1.0 performance magnitude
    is_positive: bool = True
    signal_action: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[object]]:
        return {
            "symbol": self.symbol,
            "display_name": self.display_name,
            "category": self.category.value,
            "change_24h_percent": self.change_24h_percent,
            "intensity": self.intensity,
            "is_positive": self.is_positive,
            "signal_action": self.signal_action,
        }


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

    def to_dict(self) -> Dict[str, Optional[object]]:
        return {
            "items": [item.to_dict() for item in self.items],
            "heatmap_tiles": [tile.to_dict() for tile in self.heatmap_tiles],
            "total_count": self.total_count,
            "applied_category": self.applied_category.value if self.applied_category else None,
            "applied_search": self.applied_search,
        }

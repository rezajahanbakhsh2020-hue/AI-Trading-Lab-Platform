"""Market Screener and Heatmap Service with Security Boundary enforcement."""

import math
from typing import List, Optional

from src.platform.domain.security import Permission
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.domain.screener import (
    AssetCategory,
    HeatmapTile,
    MarketScreenerFilter,
    MarketScreenerItem,
    MarketScreenerResult,
)
from src.platform.services.security import SecretSanitizer, SecurityBoundaryService


class MarketScreenerService:
    """Provides market screening, heatmap computations, and multi-asset intelligence.

    Enforces Security Boundary authorization for signal predictions and redacts sensitive data.
    """

    def __init__(self, security_service: Optional[SecurityBoundaryService] = None) -> None:
        self.security_service = security_service or SecurityBoundaryService()
        self._default_catalog = self._build_default_catalog()

    def _build_default_catalog(self) -> List[MarketScreenerItem]:
        """Base catalog of multi-asset instruments for screening and heatmap visualizer."""
        return [
            MarketScreenerItem(
                symbol="XAUUSD",
                display_name="Gold / US Dollar",
                category=AssetCategory.COMMODITIES,
                price=2685.50,
                change_24h_percent=1.42,
                volume_24h_usd=45200000000.0,
                volatility_percent=1.12,
                signal_action="BUY",
                signal_confidence=0.88,
            ),
            MarketScreenerItem(
                symbol="XAGUSD",
                display_name="Silver / US Dollar",
                category=AssetCategory.COMMODITIES,
                price=31.40,
                change_24h_percent=2.15,
                volume_24h_usd=8700000000.0,
                volatility_percent=1.85,
                signal_action="BUY",
                signal_confidence=0.81,
            ),
            MarketScreenerItem(
                symbol="EURUSD",
                display_name="Euro / US Dollar",
                category=AssetCategory.FOREX,
                price=1.0845,
                change_24h_percent=-0.35,
                volume_24h_usd=120000000000.0,
                volatility_percent=0.45,
                signal_action="HOLD",
                signal_confidence=0.60,
            ),
            MarketScreenerItem(
                symbol="GBPUSD",
                display_name="British Pound / US Dollar",
                category=AssetCategory.FOREX,
                price=1.2980,
                change_24h_percent=0.12,
                volume_24h_usd=85000000000.0,
                volatility_percent=0.58,
                signal_action="HOLD",
                signal_confidence=0.65,
            ),
            MarketScreenerItem(
                symbol="USDJPY",
                display_name="US Dollar / Japanese Yen",
                category=AssetCategory.FOREX,
                price=152.30,
                change_24h_percent=0.78,
                volume_24h_usd=98000000000.0,
                volatility_percent=0.72,
                signal_action="BUY",
                signal_confidence=0.79,
            ),
            MarketScreenerItem(
                symbol="BTCUSD",
                display_name="Bitcoin / US Dollar",
                category=AssetCategory.CRYPTO,
                price=68450.00,
                change_24h_percent=3.85,
                volume_24h_usd=38000000000.0,
                volatility_percent=3.10,
                signal_action="BUY",
                signal_confidence=0.92,
            ),
            MarketScreenerItem(
                symbol="ETHUSD",
                display_name="Ethereum / US Dollar",
                category=AssetCategory.CRYPTO,
                price=2640.00,
                change_24h_percent=-1.20,
                volume_24h_usd=19000000000.0,
                volatility_percent=3.65,
                signal_action="SELL",
                signal_confidence=0.74,
            ),
            MarketScreenerItem(
                symbol="SOLUSD",
                display_name="Solana / US Dollar",
                category=AssetCategory.CRYPTO,
                price=175.20,
                change_24h_percent=5.40,
                volume_24h_usd=6200000000.0,
                volatility_percent=4.80,
                signal_action="BUY",
                signal_confidence=0.85,
            ),
            MarketScreenerItem(
                symbol="SPX500",
                display_name="S&P 500 Index",
                category=AssetCategory.INDICES,
                price=5860.20,
                change_24h_percent=0.45,
                volume_24h_usd=65000000000.0,
                volatility_percent=0.82,
                signal_action="BUY",
                signal_confidence=0.77,
            ),
            MarketScreenerItem(
                symbol="NAS100",
                display_name="Nasdaq 100 Index",
                category=AssetCategory.INDICES,
                price=20350.80,
                change_24h_percent=0.92,
                volume_24h_usd=72000000000.0,
                volatility_percent=1.15,
                signal_action="BUY",
                signal_confidence=0.83,
            ),
        ]

    def screen_markets(
        self,
        filter_criteria: Optional[MarketScreenerFilter] = None,
        user_context: Optional[UserAuthorization] = None,
    ) -> MarketScreenerResult:
        """Query and filter market items with security authorization for signal actions."""
        criteria = filter_criteria or MarketScreenerFilter()
        user = user_context or UserAuthorization(user_id="guest", role="GUEST", permissions=frozenset())

        # Check authorization for viewing signal details
        is_allowed, _ = self.security_service.authorize(
            user, resource="signals", required_permission=Permission.READ_SIGNALS
        )

        sanitized_query = (
            SecretSanitizer.sanitize_string(criteria.search_query.strip().upper())
            if criteria.search_query
            else None
        )

        filtered_items: List[MarketScreenerItem] = []

        for item in self._default_catalog:
            # Apply category filter
            if criteria.category and item.category != criteria.category:
                continue

            # Apply min volume filter
            if criteria.min_volume_usd and item.volume_24h_usd < criteria.min_volume_usd:
                continue

            # Apply search filter
            if sanitized_query:
                if (
                    sanitized_query not in item.symbol.upper()
                    and sanitized_query not in item.display_name.upper()
                ):
                    continue

            # Apply signal filter
            if criteria.signal_filter:
                if not is_allowed or item.signal_action != criteria.signal_filter.upper():
                    continue

            # Sanitize signal outputs based on permissions
            sanitized_item = MarketScreenerItem(
                symbol=item.symbol,
                display_name=item.display_name,
                category=item.category,
                price=item.price,
                change_24h_percent=item.change_24h_percent,
                volume_24h_usd=item.volume_24h_usd,
                volatility_percent=item.volatility_percent,
                signal_action=item.signal_action if is_allowed else None,
                signal_confidence=item.signal_confidence if is_allowed else None,
                extra_metadata=item.extra_metadata,
            )
            filtered_items.append(sanitized_item)

        # Sort items
        sort_key = criteria.sort_by if hasattr(MarketScreenerItem, criteria.sort_by) else "change_24h_percent"
        filtered_items.sort(
            key=lambda x: getattr(x, sort_key, 0.0),
            reverse=criteria.sort_descending,
        )

        # Generate Heatmap Tiles
        heatmap_tiles = self._generate_heatmap_tiles(filtered_items)

        return MarketScreenerResult(
            items=filtered_items,
            heatmap_tiles=heatmap_tiles,
            total_count=len(filtered_items),
            applied_category=criteria.category,
            applied_search=sanitized_query,
        )

    def _generate_heatmap_tiles(self, items: List[MarketScreenerItem]) -> List[HeatmapTile]:
        """Convert screener items to normalized Heatmap Tiles."""
        if not items:
            return []

        max_change = max(abs(item.change_24h_percent) for item in items) or 1.0

        tiles: List[HeatmapTile] = []
        for item in items:
            intensity = min(1.0, abs(item.change_24h_percent) / max_change) if max_change > 0 else 0.5
            tiles.append(
                HeatmapTile(
                    symbol=item.symbol,
                    display_name=item.display_name,
                    category=item.category,
                    change_24h_percent=item.change_24h_percent,
                    intensity=round(intensity, 2),
                    is_positive=item.change_24h_percent >= 0,
                    signal_action=item.signal_action,
                )
            )
        return tiles

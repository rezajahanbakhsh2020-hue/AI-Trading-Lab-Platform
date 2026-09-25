"""Market Screener and Heatmap Service with Security Boundary enforcement."""

from typing import Any, Dict, List, Optional, Tuple

from src.platform.domain.screener import (
    AssetCategory,
    HeatmapTile,
    MarketScreenerFilter,
    MarketScreenerItem,
    MarketScreenerResult,
)
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.provider_operations import ProviderOperations
from src.platform.services.security import SecretSanitizer, SecurityBoundaryService

# Canonical Instrument Registry for Screener scanning
INSTRUMENT_CATALOG: List[Tuple[str, str, AssetCategory]] = [
    ("XAUUSD", "Gold / US Dollar", AssetCategory.COMMODITIES),
    ("XAGUSD", "Silver / US Dollar", AssetCategory.COMMODITIES),
    ("EURUSD", "Euro / US Dollar", AssetCategory.FOREX),
    ("GBPUSD", "British Pound / US Dollar", AssetCategory.FOREX),
    ("USDJPY", "US Dollar / Japanese Yen", AssetCategory.FOREX),
    ("BTCUSD", "Bitcoin / US Dollar", AssetCategory.CRYPTO),
    ("ETHUSD", "Ethereum / US Dollar", AssetCategory.CRYPTO),
    ("SOLUSD", "Solana / US Dollar", AssetCategory.CRYPTO),
    ("SPX500", "S&P 500 Index", AssetCategory.INDICES),
    ("NAS100", "Nasdaq 100 Index", AssetCategory.INDICES),
]


class MarketScreenerService:
    """Provides market screening, heatmap computations, and multi-asset intelligence.

    Uses truthful runtime provider operations and Project 1 signal presenter boundaries.
    Enforces Security Boundary authorization for signal predictions and redacts sensitive data.
    """

    def __init__(
        self,
        security_service: Optional[SecurityBoundaryService] = None,
        provider_operations: Optional[ProviderOperations] = None,
        signal_presenter: Optional[Any] = None,
    ) -> None:
        self.security_service = security_service or SecurityBoundaryService()
        self._provider_ops = provider_operations
        self._signal_presenter = signal_presenter

    def _fetch_runtime_item(
        self,
        symbol: str,
        display_name: str,
        category: AssetCategory,
        is_signal_allowed: bool,
        user_context: Optional[UserAuthorization] = None,
    ) -> MarketScreenerItem:
        """Fetch truthful runtime market quote and signal for a canonical instrument."""
        price: Optional[float] = None
        change_24h_percent: Optional[float] = None
        volume_24h_usd: Optional[float] = None
        volatility_percent: Optional[float] = None  # Always None unless supplied by provider

        # 1. Fetch quote through runtime ProviderOperations
        if self._provider_ops is not None:
            try:
                res = self._provider_ops.fetch_quote(provider_id="biquote", symbol=symbol)
                quote = res.quote
                if quote and quote.symbol.strip().upper() == symbol.strip().upper():
                    price = quote.last if (quote.last is not None and quote.last > 0) else quote.mid
                    change_24h_percent = quote.change_percent
                    volume_24h_usd = getattr(quote, "volume24h", None)
            except Exception:
                price = None
                change_24h_percent = None
                volume_24h_usd = None

        # 2. Fetch signal through runtime Project1SignalPresenter
        signal_action: Optional[str] = None
        signal_confidence: Optional[float] = None

        if self._signal_presenter is not None and is_signal_allowed:
            try:
                pres = self._signal_presenter.present_signal(
                    symbol=symbol,
                    timeframe="1h",
                    user=user_context,
                )
                if pres.get("status") == "active" and pres.get("signal"):
                    sig = pres["signal"]
                    if (sig.get("symbol") or "").strip().upper() == symbol.strip().upper():
                        signal_action = (sig.get("signal_type") or "").upper()
                        signal_confidence = sig.get("confidence")
            except Exception:
                signal_action = None
                signal_confidence = None

        return MarketScreenerItem(
            symbol=symbol,
            display_name=display_name,
            category=category,
            price=price,
            change_24h_percent=change_24h_percent,
            volume_24h_usd=volume_24h_usd,
            volatility_percent=volatility_percent,
            signal_action=signal_action,
            signal_confidence=signal_confidence,
        )

    def screen_markets(
        self,
        filter_criteria: Optional[MarketScreenerFilter] = None,
        user_context: Optional[UserAuthorization] = None,
    ) -> MarketScreenerResult:
        """Query and filter market items with security authorization for signal actions."""
        criteria = filter_criteria or MarketScreenerFilter()
        user = user_context or UserAuthorization(
            user_id="guest",
            auth_code="code_guest",
            role=UserRole.GUEST,
            permissions=frozenset(),
        )

        # Check authorization for viewing signal details
        is_allowed, _ = self.security_service.authorize(
            user, resource="signals", required_permission=Permission.READ_SIGNALS
        )

        sanitized_query = (
            SecretSanitizer.sanitize_string(criteria.search_query.strip().upper())
            if criteria.search_query
            else None
        )

        raw_items: List[MarketScreenerItem] = []
        for symbol, display_name, category in INSTRUMENT_CATALOG:
            item = self._fetch_runtime_item(
                symbol=symbol,
                display_name=display_name,
                category=category,
                is_signal_allowed=is_allowed,
                user_context=user,
            )
            raw_items.append(item)

        filtered_items: List[MarketScreenerItem] = []

        for item in raw_items:
            # Apply category filter
            if criteria.category and item.category != criteria.category:
                continue

            # Apply min volume filter
            if criteria.min_volume_usd:
                if item.volume_24h_usd is None or item.volume_24h_usd < criteria.min_volume_usd:
                    continue

            # Apply search filter
            if sanitized_query:
                if (
                    sanitized_query not in item.symbol.upper()
                    and sanitized_query not in item.display_name.upper()
                ):
                    continue

            # Apply signal filter
            if criteria.signal_filter and criteria.signal_filter.upper() != "ALL":
                if not is_allowed:
                    continue
                req_sig = criteria.signal_filter.upper()
                if req_sig == "NO SIGNAL":
                    if item.signal_action is not None:
                        continue
                else:
                    if item.signal_action != req_sig:
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

        def get_sort_val(x: MarketScreenerItem) -> float:
            val = getattr(x, sort_key, None)
            if val is None:
                return -999999999.0 if criteria.sort_descending else 999999999.0
            return float(val)

        filtered_items.sort(
            key=get_sort_val,
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

        valid_changes = [abs(item.change_24h_percent) for item in items if item.change_24h_percent is not None]
        max_change = max(valid_changes) if valid_changes else 1.0
        if max_change <= 0:
            max_change = 1.0

        tiles: List[HeatmapTile] = []
        for item in items:
            if item.change_24h_percent is not None:
                intensity = min(1.0, abs(item.change_24h_percent) / max_change)
                is_pos = item.change_24h_percent >= 0
            else:
                intensity = 0.0
                is_pos = True

            tiles.append(
                HeatmapTile(
                    symbol=item.symbol,
                    display_name=item.display_name,
                    category=item.category,
                    change_24h_percent=item.change_24h_percent,
                    intensity=round(intensity, 2),
                    is_positive=is_pos,
                    signal_action=item.signal_action,
                )
            )
        return tiles

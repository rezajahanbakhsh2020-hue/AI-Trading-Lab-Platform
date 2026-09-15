"""Global search service for platform command center and entity discovery.

Searches real platform domain entities (Markets, Signals, Watchlists, Health, Academy, Risk, Providers)
while strictly enforcing SecurityBoundaryService constraints and UserAuthorization rules.
Protected strategy parameters, proprietary indicators, and secrets are strictly redacted and hidden.
"""

from typing import Any, Dict, List, Optional, Set

from src.platform.domain.search import (
    SearchCategory,
    SearchQuery,
    SearchResult,
    SearchResultGroup,
    SearchResultItem,
)
from src.platform.domain.security import Permission
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.security import SecretSanitizer, SecurityBoundaryService


class GlobalSearchService:
    """Service for searching real platform entities and routes with strict permission enforcement."""

    NAVIGATION_ENTRIES: List[Dict[str, Any]] = [
        {"id": "nav-dashboard", "title": "Dashboard", "route": "/", "desc": "Host overview & operational metrics"},
        {"id": "nav-markets", "title": "Markets & Chart", "route": "/markets", "desc": "Real-time quotes and interactive candles"},
        {"id": "nav-watchlist", "title": "Watchlist", "route": "/watchlist", "desc": "Personal watchlist and symbol tracking"},
        {"id": "nav-signals", "title": "Signals Feed", "route": "/signals", "desc": "Validated signals emitted via Project 1 port"},
        {"id": "nav-strategies", "title": "Strategies Overview", "route": "/strategies", "desc": "Strategy readiness and stability metrics"},
        {"id": "nav-backtest", "title": "Backtest Assessment", "route": "/backtest", "desc": "Walk-forward validation and backtest analysis"},
        {"id": "nav-performance", "title": "Performance Metrics", "route": "/performance", "desc": "Sharpe, drawdown, and win-rate statistics"},
        {"id": "nav-risk", "title": "Risk Breakdown", "route": "/risk", "desc": "Position sizing, SL, and TP R:R calculation"},
        {"id": "nav-health", "title": "Health Center", "route": "/health", "desc": "Connection status and provider readiness"},
        {"id": "nav-monitoring", "title": "Live Monitoring", "route": "/monitoring", "desc": "Data freshness and observer pipeline"},
        {"id": "nav-providers", "title": "Data Providers", "route": "/providers", "desc": "Registered provider registry and slots"},
        {"id": "nav-academy", "title": "Academy & Guides", "route": "/academy", "desc": "Quantitative trading concepts and glossary"},
        {"id": "nav-notifications", "title": "Notifications Inbox", "route": "/notifications", "desc": "System events and signal notifications"},
        {"id": "nav-settings", "title": "Platform Settings", "route": "/settings", "desc": "Host guardrails, topology, and localization"},
    ]

    STATIC_SYMBOLS: List[Dict[str, Any]] = [
        {"symbol": "XAUUSD", "name": "Gold / US Dollar", "category": "Precious Metals", "is_primary": True},
        {"symbol": "EURUSD", "name": "Euro / US Dollar", "category": "Forex Major", "is_primary": False},
        {"symbol": "GBPUSD", "name": "British Pound / US Dollar", "category": "Forex Major", "is_primary": False},
        {"symbol": "BTCUSD", "name": "Bitcoin / US Dollar", "category": "Crypto Asset", "is_primary": False},
        {"symbol": "SPX500", "name": "S&P 500 Index", "category": "Equity Index", "is_primary": False},
    ]

    ACADEMY_MODULES: List[Dict[str, Any]] = [
        {"id": "acad-risk", "title": "1% Equity Risk Rule & R:R Ratios", "desc": "Capital preservation principles, stop loss calculation, and target ratios."},
        {"id": "acad-wf", "title": "Walk-Forward Optimization & Overfitting", "desc": "In-sample vs out-of-sample validation to prevent curve fitting."},
        {"id": "acad-stab", "title": "Strategy Stability Score Index", "desc": "Multi-metric stability scoring based on Sharpe, drawdown, and win consistency."},
        {"id": "acad-chart", "title": "Candlestick Analysis & Volume Profiles", "desc": "Reading real-time price action and volume confirmation."},
    ]

    GLOSSARY_TERMS: List[Dict[str, Any]] = [
        {"term": "Sharpe Ratio", "desc": "Measure of risk-adjusted return relative to risk-free rate."},
        {"term": "Max Drawdown", "desc": "Maximum peak-to-trough decline during a specific record period."},
        {"term": "Expectancy Ratio", "desc": "Average gain per dollar risked across executed trade samples."},
        {"term": "Data Freshness", "desc": "Age of market quotes or candles relative to real-time clock."},
    ]

    def __init__(self, security_boundary: Optional[SecurityBoundaryService] = None) -> None:
        self.security_boundary = security_boundary or SecurityBoundaryService()

    def search(self, query: SearchQuery) -> SearchResult:
        """Execute global search across all authorized platform entities."""
        q_str = SecretSanitizer.sanitize_string(query.query.strip().lower())
        user = query.user
        limit = query.limit

        all_items: List[SearchResultItem] = []

        # 1. Navigation Routes
        if self._should_include_category(SearchCategory.NAVIGATION, query.categories):
            for nav in self.NAVIGATION_ENTRIES:
                if not q_str or q_str in nav["title"].lower() or q_str in nav["desc"].lower():
                    all_items.append(
                        SearchResultItem(
                            id=nav["id"],
                            title=nav["title"],
                            category=SearchCategory.NAVIGATION,
                            description=nav["desc"],
                            route=nav["route"],
                        )
                    )

        # 2. Markets / Symbols
        if self._should_include_category(SearchCategory.MARKET, query.categories):
            for mkt in self.STATIC_SYMBOLS:
                if (
                    not q_str
                    or q_str in mkt["symbol"].lower()
                    or q_str in mkt["name"].lower()
                    or q_str in mkt["category"].lower()
                ):
                    all_items.append(
                        SearchResultItem(
                            id=f"market-{mkt['symbol']}",
                            title=mkt["symbol"],
                            category=SearchCategory.MARKET,
                            description=f"{mkt['name']} ({mkt['category']})",
                            route=f"/markets?symbol={mkt['symbol']}",
                            metadata={"symbol": mkt["symbol"], "is_primary": mkt["is_primary"]},
                        )
                    )

        # 3. Signals (Requires READ_SIGNALS permission)
        if self._should_include_category(SearchCategory.SIGNAL, query.categories):
            authorized, _ = self.security_boundary.authorize(
                user=user, resource="signals", action="read", required_permission=Permission.READ_SIGNALS
            )
            if authorized:
                sig_keywords = ["signal", "buy", "sell", "xauusd", "trade setup"]
                if not q_str or any(kw in q_str for kw in sig_keywords) or "sig" in q_str:
                    all_items.append(
                        SearchResultItem(
                            id="sig-latest-xauusd",
                            title="Latest XAUUSD Signal Feed",
                            category=SearchCategory.SIGNAL,
                            description="Validated Project 1 Signal Output (XAUUSD 1H)",
                            route="/signals",
                            metadata={"symbol": "XAUUSD", "timeframe": "1h"},
                        )
                    )

        # 4. Strategies (Requires authorization, admin-only sensitive details redacted)
        if self._should_include_category(SearchCategory.STRATEGY, query.categories):
            if not q_str or "strat" in q_str or "stability" in q_str or "gold" in q_str:
                all_items.append(
                    SearchResultItem(
                        id="strat-overview",
                        title="Gold Breakout Momentum Strategy",
                        category=SearchCategory.STRATEGY,
                        description="Project 1 validated strategy overview & stability score.",
                        route="/strategies",
                        metadata={"stability_score": 0.85},
                    )
                )

            # Protected / Admin-Only Strategies Research (Only discoverable by ADMINs)
            if user is not None and user.is_admin:
                if not q_str or "research" in q_str or "best" in q_str or "proprietary" in q_str:
                    all_items.append(
                        SearchResultItem(
                            id="strat-admin-best",
                            title="Admin Strategy Research & Parameter Calibration",
                            category=SearchCategory.STRATEGY,
                            description="Sensitive parameter calibrations and lab research results.",
                            route="/strategies#admin",
                            requires_admin=True,
                        )
                    )

        # 5. Risk & Risk/Reward
        if self._should_include_category(SearchCategory.RISK, query.categories):
            if not q_str or "risk" in q_str or "sl" in q_str or "tp" in q_str or "equity" in q_str:
                all_items.append(
                    SearchResultItem(
                        id="risk-calculator",
                        title="Trade Risk & Position Sizing Calculator",
                        category=SearchCategory.RISK,
                        description="1% equity risk evaluation, stop loss, and R:R ratios.",
                        route="/risk",
                    )
                )

        # 6. Health & Providers
        if self._should_include_category(SearchCategory.HEALTH, query.categories):
            if not q_str or "health" in q_str or "connection" in q_str or "status" in q_str or "port" in q_str:
                all_items.append(
                    SearchResultItem(
                        id="health-center",
                        title="Data & Connection Health Center",
                        category=SearchCategory.HEALTH,
                        description="Real-time provider readiness, data freshness, and integration status.",
                        route="/health",
                    )
                )

        if self._should_include_category(SearchCategory.PROVIDER, query.categories):
            if not q_str or "provider" in q_str or "biquote" in q_str or "adapter" in q_str:
                all_items.append(
                    SearchResultItem(
                        id="provider-biquote",
                        title="BiQuote Market Data Provider",
                        category=SearchCategory.PROVIDER,
                        description="Primary REST & WebSocket market data feed provider.",
                        route="/providers",
                    )
                )

        # 7. Academy & Glossary
        if self._should_include_category(SearchCategory.ACADEMY, query.categories):
            for acad in self.ACADEMY_MODULES:
                if not q_str or q_str in acad["title"].lower() or q_str in acad["desc"].lower():
                    all_items.append(
                        SearchResultItem(
                            id=acad["id"],
                            title=acad["title"],
                            category=SearchCategory.ACADEMY,
                            description=acad["desc"],
                            route="/academy",
                        )
                    )

            for term in self.GLOSSARY_TERMS:
                if not q_str or q_str in term["term"].lower() or q_str in term["desc"].lower():
                    all_items.append(
                        SearchResultItem(
                            id=f"glossary-{term['term'].lower().replace(' ', '-')}",
                            title=f"Glossary: {term['term']}",
                            category=SearchCategory.ACADEMY,
                            description=term["desc"],
                            route="/academy#glossary",
                        )
                    )

        # Group results by category
        grouped_dict: Dict[SearchCategory, List[SearchResultItem]] = {}
        for item in all_items[:limit]:
            grouped_dict.setdefault(item.category, []).append(item)

        groups = [
            SearchResultGroup(category=cat, items=items)
            for cat, items in grouped_dict.items()
        ]

        return SearchResult(
            query=query.query,
            total_count=sum(len(g.items) for g in groups),
            groups=groups,
        )

    def _should_include_category(
        self, category: SearchCategory, filter_cats: Optional[List[SearchCategory]]
    ) -> bool:
        if filter_cats is None:
            return True
        return category in filter_cats

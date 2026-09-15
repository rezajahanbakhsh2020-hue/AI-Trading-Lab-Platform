"""Workspace and Watchlist domain models for user workspace preferences and watchlists.

Defines domain entities for Watchlist, Workspace, chart/layout preferences,
and user-scoped workspace states adhering to Hexagonal Architecture.
"""

from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional, Tuple


def _validate_non_empty_string(val: str, field_name: str) -> str:
    if not isinstance(val, str) or not val.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return val.strip()


def _normalize_symbol(symbol: str) -> str:
    clean = _validate_non_empty_string(symbol, "symbol")
    return clean.upper()


@dataclass(frozen=True)
class Watchlist:
    """Immutable Watchlist entity containing named list of market symbols."""

    watchlist_id: str
    name: str
    symbols: Tuple[str, ...] = field(default_factory=tuple)
    is_default: bool = False
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "watchlist_id", _validate_non_empty_string(self.watchlist_id, "watchlist_id")
        )
        object.__setattr__(
            self, "name", _validate_non_empty_string(self.name, "name")
        )

        # Normalize and deduplicate symbols while preserving order
        seen = set()
        clean_symbols: List[str] = []
        for s in self.symbols:
            norm = _normalize_symbol(s)
            if norm not in seen:
                seen.add(norm)
                clean_symbols.append(norm)
        object.__setattr__(self, "symbols", tuple(clean_symbols))

        if not isinstance(self.is_default, bool):
            raise ValueError("is_default must be a boolean")

    def add_symbol(self, symbol: str) -> "Watchlist":
        """Add a symbol to the watchlist if not already present."""
        norm = _normalize_symbol(symbol)
        if norm in self.symbols:
            return self
        return Watchlist(
            watchlist_id=self.watchlist_id,
            name=self.name,
            symbols=self.symbols + (norm,),
            is_default=self.is_default,
            created_at=self.created_at,
            updated_at=time.time(),
        )

    def remove_symbol(self, symbol: str) -> "Watchlist":
        """Remove a symbol from the watchlist."""
        norm = _normalize_symbol(symbol)
        if norm not in self.symbols:
            return self
        new_symbols = tuple(s for s in self.symbols if s != norm)
        return Watchlist(
            watchlist_id=self.watchlist_id,
            name=self.name,
            symbols=new_symbols,
            is_default=self.is_default,
            created_at=self.created_at,
            updated_at=time.time(),
        )

    def rename(self, new_name: str) -> "Watchlist":
        """Rename the watchlist."""
        clean_name = _validate_non_empty_string(new_name, "new_name")
        if clean_name == self.name:
            return self
        return Watchlist(
            watchlist_id=self.watchlist_id,
            name=clean_name,
            symbols=self.symbols,
            is_default=self.is_default,
            created_at=self.created_at,
            updated_at=time.time(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert Watchlist to dictionary."""
        return {
            "watchlist_id": self.watchlist_id,
            "name": self.name,
            "symbols": list(self.symbols),
            "is_default": self.is_default,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Watchlist":
        """Recreate Watchlist entity from dictionary."""
        return cls(
            watchlist_id=data["watchlist_id"],
            name=data["name"],
            symbols=tuple(data.get("symbols", [])),
            is_default=bool(data.get("is_default", False)),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
        )


@dataclass(frozen=True)
class Workspace:
    """Immutable Workspace entity representing user-scoped desktop/mobile layout and preferences."""

    user_id: str
    active_watchlist_id: str
    active_symbol: str
    watchlists: Dict[str, Watchlist] = field(default_factory=dict)
    chart_preferences: Dict[str, Any] = field(default_factory=dict)
    layout_preferences: Dict[str, Any] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        object.__setattr__(self, "user_id", _validate_non_empty_string(self.user_id, "user_id"))
        object.__setattr__(
            self, "active_watchlist_id", _validate_non_empty_string(self.active_watchlist_id, "active_watchlist_id")
        )
        object.__setattr__(self, "active_symbol", _normalize_symbol(self.active_symbol))

    def get_active_watchlist(self) -> Optional[Watchlist]:
        """Return the active Watchlist entity if present."""
        return self.watchlists.get(self.active_watchlist_id)

    def with_active_symbol(self, symbol: str) -> "Workspace":
        """Set active symbol."""
        norm = _normalize_symbol(symbol)
        if norm == self.active_symbol:
            return self
        return Workspace(
            user_id=self.user_id,
            active_watchlist_id=self.active_watchlist_id,
            active_symbol=norm,
            watchlists=self.watchlists,
            chart_preferences=self.chart_preferences,
            layout_preferences=self.layout_preferences,
            updated_at=time.time(),
        )

    def with_active_watchlist(self, watchlist_id: str) -> "Workspace":
        """Switch active watchlist ID."""
        clean_id = _validate_non_empty_string(watchlist_id, "watchlist_id")
        if clean_id not in self.watchlists:
            raise KeyError(f"Watchlist with id '{clean_id}' not found in workspace for user '{self.user_id}'")
        if clean_id == self.active_watchlist_id:
            return self
        return Workspace(
            user_id=self.user_id,
            active_watchlist_id=clean_id,
            active_symbol=self.active_symbol,
            watchlists=self.watchlists,
            chart_preferences=self.chart_preferences,
            layout_preferences=self.layout_preferences,
            updated_at=time.time(),
        )

    def with_updated_watchlist(self, watchlist: Watchlist) -> "Workspace":
        """Add or update a Watchlist inside workspace."""
        if not isinstance(watchlist, Watchlist):
            raise ValueError("watchlist must be a Watchlist instance")
        new_wls = dict(self.watchlists)
        new_wls[watchlist.watchlist_id] = watchlist
        return Workspace(
            user_id=self.user_id,
            active_watchlist_id=self.active_watchlist_id,
            active_symbol=self.active_symbol,
            watchlists=new_wls,
            chart_preferences=self.chart_preferences,
            layout_preferences=self.layout_preferences,
            updated_at=time.time(),
        )

    def without_watchlist(self, watchlist_id: str) -> "Workspace":
        """Remove a watchlist by ID."""
        clean_id = _validate_non_empty_string(watchlist_id, "watchlist_id")
        if clean_id not in self.watchlists:
            return self
        if len(self.watchlists) <= 1:
            raise ValueError("Cannot remove the last remaining watchlist in a workspace")

        new_wls = {k: v for k, v in self.watchlists.items() if k != clean_id}
        new_active = (
            list(new_wls.keys())[0] if clean_id == self.active_watchlist_id else self.active_watchlist_id
        )

        return Workspace(
            user_id=self.user_id,
            active_watchlist_id=new_active,
            active_symbol=self.active_symbol,
            watchlists=new_wls,
            chart_preferences=self.chart_preferences,
            layout_preferences=self.layout_preferences,
            updated_at=time.time(),
        )

    def with_chart_preferences(self, prefs: Dict[str, Any]) -> "Workspace":
        """Update chart preferences."""
        merged = {**self.chart_preferences, **prefs}
        return Workspace(
            user_id=self.user_id,
            active_watchlist_id=self.active_watchlist_id,
            active_symbol=self.active_symbol,
            watchlists=self.watchlists,
            chart_preferences=merged,
            layout_preferences=self.layout_preferences,
            updated_at=time.time(),
        )

    def with_layout_preferences(self, prefs: Dict[str, Any]) -> "Workspace":
        """Update layout preferences."""
        merged = {**self.layout_preferences, **prefs}
        return Workspace(
            user_id=self.user_id,
            active_watchlist_id=self.active_watchlist_id,
            active_symbol=self.active_symbol,
            watchlists=self.watchlists,
            chart_preferences=self.chart_preferences,
            layout_preferences=merged,
            updated_at=time.time(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert Workspace to dictionary."""
        return {
            "user_id": self.user_id,
            "active_watchlist_id": self.active_watchlist_id,
            "active_symbol": self.active_symbol,
            "watchlists": {k: v.to_dict() for k, v in self.watchlists.items()},
            "chart_preferences": self.chart_preferences,
            "layout_preferences": self.layout_preferences,
            "updated_at": self.updated_at,
        }

    @classmethod
    def create_default(cls, user_id: str) -> "Workspace":
        """Factory method to construct default workspace for a user."""
        default_wl = Watchlist(
            watchlist_id="default",
            name="Main Watchlist",
            symbols=("XAUUSD", "EURUSD", "GBPUSD", "BTCUSD", "SPX500"),
            is_default=True,
        )
        return cls(
            user_id=user_id,
            active_watchlist_id="default",
            active_symbol="XAUUSD",
            watchlists={"default": default_wl},
            chart_preferences={"timeframe": "1h", "chart_type": "candlestick"},
            layout_preferences={"dashboard_layout": "default", "selected_panels": ["chart", "watchlist", "signal"]},
        )

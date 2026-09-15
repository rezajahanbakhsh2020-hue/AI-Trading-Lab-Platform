"""Global search and command center domain models.

Defines search query inputs, result items, categories, and grouped search response structures.
Enforces security constraints for protected trading information.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.security import SecretSanitizer


class SearchCategory(str, Enum):
    """Categories for indexing and grouping platform search results."""

    MARKET = "market"
    SIGNAL = "signal"
    WATCHLIST = "watchlist"
    STRATEGY = "strategy"
    NAVIGATION = "navigation"
    NOTIFICATION = "notification"
    PROVIDER = "provider"
    HEALTH = "health"
    RISK = "risk"
    ACADEMY = "academy"
    SETTING = "setting"


@dataclass(frozen=True)
class SearchResultItem:
    """Individual search result item representations."""

    id: str
    title: str
    category: SearchCategory
    description: Optional[str] = None
    route: str = "/"
    metadata: Dict[str, Any] = field(default_factory=dict)
    requires_admin: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("id must be a non-empty string")
        object.__setattr__(self, "id", self.id.strip())

        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title must be a non-empty string")
        object.__setattr__(self, "title", self.title.strip())

        if not isinstance(self.category, SearchCategory):
            raise ValueError(f"category must be a SearchCategory, got {type(self.category)}")

        if self.description is not None and not isinstance(self.description, str):
            raise ValueError("description must be a string if provided")

        if not isinstance(self.route, str) or not self.route.strip():
            raise ValueError("route must be a non-empty string")
        object.__setattr__(self, "route", self.route.strip())

    def to_dict(self) -> Dict[str, Any]:
        """Convert search result item to dict format."""
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category.value,
            "description": self.description,
            "route": self.route,
            "metadata": dict(self.metadata),
            "requires_admin": self.requires_admin,
        }


@dataclass(frozen=True)
class SearchQuery:
    """Input query specification for global search execution."""

    query: str
    user: Optional[UserAuthorization] = None
    categories: Optional[List[SearchCategory]] = None
    limit: int = 20

    def __post_init__(self) -> None:
        clean_q = self.query.strip() if isinstance(self.query, str) else ""
        clean_q = SecretSanitizer.sanitize_string(clean_q)
        object.__setattr__(self, "query", clean_q)

        if not isinstance(self.limit, int) or self.limit <= 0:
            raise ValueError("limit must be a positive integer")


@dataclass(frozen=True)
class SearchResultGroup:
    """Grouped search items categorized by domain entity type."""

    category: SearchCategory
    items: List[SearchResultItem]

    def to_dict(self) -> Dict[str, Any]:
        """Convert group to dictionary representation."""
        return {
            "category": self.category.value,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(frozen=True)
class SearchResult:
    """Complete response payload for global search query."""

    query: str
    total_count: int
    groups: List[SearchResultGroup]

    def to_dict(self) -> Dict[str, Any]:
        """Convert search result to dictionary representation."""
        return {
            "query": self.query,
            "total_count": self.total_count,
            "groups": [group.to_dict() for group in self.groups],
        }

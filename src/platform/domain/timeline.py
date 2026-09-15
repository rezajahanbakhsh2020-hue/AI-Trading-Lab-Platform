"""Domain models for Unified Intelligence Timeline & Explainability Boundary.

Defines timeline categories, severity levels, timeline items, and explainability payloads
with immutability and strict schema validation.
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, List, Optional


class TimelineCategory(str, Enum):
    """Categories of intelligence timeline events."""

    MARKET = "market"
    SIGNAL = "signal"
    NOTIFICATION = "notification"
    HEALTH = "health"
    WORKSPACE = "workspace"
    MARKET_INTELLIGENCE = "market_intelligence"
    SYSTEM = "system"


class TimelineSeverity(str, Enum):
    """Severity levels for timeline items."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class TimelineItem:
    """Domain model representing a single real chronological timeline event."""

    item_id: str
    timestamp: float
    category: TimelineCategory
    severity: TimelineSeverity
    title: str
    summary: str
    source: str
    route: str
    target_user_id: Optional[str] = None
    explainable: bool = False
    payload: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.item_id, str) or not self.item_id.strip():
            raise ValueError("item_id must be a non-empty string")
        object.__setattr__(self, "item_id", self.item_id.strip())

        if not isinstance(self.timestamp, (int, float)) or self.timestamp < 0:
            raise ValueError("timestamp must be a non-negative real number")
        object.__setattr__(self, "timestamp", float(self.timestamp))

        if not isinstance(self.category, TimelineCategory):
            if isinstance(self.category, str):
                try:
                    cat = TimelineCategory(self.category.strip().lower())
                    object.__setattr__(self, "category", cat)
                except ValueError:
                    raise ValueError(f"Invalid category: {self.category}")
            else:
                raise ValueError("category must be a TimelineCategory enum or valid string")

        if not isinstance(self.severity, TimelineSeverity):
            if isinstance(self.severity, str):
                try:
                    sev = TimelineSeverity(self.severity.strip().lower())
                    object.__setattr__(self, "severity", sev)
                except ValueError:
                    raise ValueError(f"Invalid severity: {self.severity}")
            else:
                raise ValueError("severity must be a TimelineSeverity enum or valid string")

        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title must be a non-empty string")
        object.__setattr__(self, "title", self.title.strip())

        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ValueError("summary must be a non-empty string")
        object.__setattr__(self, "summary", self.summary.strip())

        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a non-empty string")
        object.__setattr__(self, "source", self.source.strip())

        if not isinstance(self.route, str) or not self.route.strip():
            raise ValueError("route must be a non-empty string")
        object.__setattr__(self, "route", self.route.strip())

        if self.target_user_id is not None:
            if not isinstance(self.target_user_id, str) or not self.target_user_id.strip():
                raise ValueError("target_user_id must be a non-empty string if provided")
            object.__setattr__(self, "target_user_id", self.target_user_id.strip())

        if not isinstance(self.explainable, bool):
            raise ValueError("explainable must be a boolean")

        if not isinstance(self.payload, dict):
            raise ValueError("payload must be a dict")

    def to_dict(self) -> Dict[str, Any]:
        """Convert timeline item to dictionary representation."""
        return {
            "item_id": self.item_id,
            "timestamp": self.timestamp,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "summary": self.summary,
            "source": self.source,
            "route": self.route,
            "target_user_id": self.target_user_id,
            "explainable": self.explainable,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class ExplainabilityPayload:
    """Domain model representing explainable context for permitted intelligence items."""

    item_id: str
    item_type: str
    received_at: float
    source: str
    freshness_status: str
    permitted_metadata: Dict[str, Any] = field(default_factory=dict)
    permitted_market_context: Dict[str, Any] = field(default_factory=dict)
    permitted_risk_context: Dict[str, Any] = field(default_factory=dict)
    explainability_notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.item_id, str) or not self.item_id.strip():
            raise ValueError("item_id must be a non-empty string")
        object.__setattr__(self, "item_id", self.item_id.strip())

        if not isinstance(self.item_type, str) or not self.item_type.strip():
            raise ValueError("item_type must be a non-empty string")
        object.__setattr__(self, "item_type", self.item_type.strip())

        if not isinstance(self.received_at, (int, float)) or self.received_at < 0:
            raise ValueError("received_at must be a non-negative real number")
        object.__setattr__(self, "received_at", float(self.received_at))

        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a non-empty string")
        object.__setattr__(self, "source", self.source.strip())

        if not isinstance(self.freshness_status, str) or not self.freshness_status.strip():
            raise ValueError("freshness_status must be a non-empty string")
        object.__setattr__(self, "freshness_status", self.freshness_status.strip())

        if not isinstance(self.permitted_metadata, dict):
            raise ValueError("permitted_metadata must be a dict")

        if not isinstance(self.permitted_market_context, dict):
            raise ValueError("permitted_market_context must be a dict")

        if not isinstance(self.permitted_risk_context, dict):
            raise ValueError("permitted_risk_context must be a dict")

        if not isinstance(self.explainability_notes, list):
            raise ValueError("explainability_notes must be a list")

    def to_dict(self) -> Dict[str, Any]:
        """Convert explainability payload to dictionary representation."""
        return {
            "item_id": self.item_id,
            "item_type": self.item_type,
            "received_at": self.received_at,
            "source": self.source,
            "freshness_status": self.freshness_status,
            "permitted_metadata": dict(self.permitted_metadata),
            "permitted_market_context": dict(self.permitted_market_context),
            "permitted_risk_context": dict(self.permitted_risk_context),
            "explainability_notes": list(self.explainability_notes),
        }

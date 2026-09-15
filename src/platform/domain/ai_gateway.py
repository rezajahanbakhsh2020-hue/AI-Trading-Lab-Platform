"""Secure AI Gateway domain models and capability contracts.

Defines AI capabilities, provider statuses, allowed intelligence contexts,
AI requests, and AI responses for the AI Gateway boundary.
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, List, Optional, Tuple, Union


class AICapability(str, Enum):
    """Safe foundation capabilities supported by the AI Gateway."""

    EXPLAIN_SIGNAL = "explain_signal"
    SUMMARIZE_MARKET = "summarize_market"
    SUMMARIZE_TIMELINE = "summarize_timeline"
    EXPLAIN_HEALTH = "explain_health"


class AIProviderStatus(str, Enum):
    """AI Provider operational statuses."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass(frozen=True)
class AllowedIntelligenceContext:
    """Explicit, minimal, user-scoped, permission-filtered, and sanitized context for AI operations."""

    context_id: str
    user_id: str
    capability: AICapability
    timestamp: float
    permitted_symbol: Optional[str] = None
    permitted_signal: Optional[Dict[str, Any]] = None
    permitted_market: Optional[Dict[str, Any]] = None
    permitted_timeline: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    permitted_health: Optional[Dict[str, Any]] = None
    is_sanitized: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.context_id, str) or not self.context_id.strip():
            raise ValueError("context_id must be a non-empty string")
        object.__setattr__(self, "context_id", self.context_id.strip())

        if not isinstance(self.user_id, str) or not self.user_id.strip():
            raise ValueError("user_id must be a non-empty string")
        object.__setattr__(self, "user_id", self.user_id.strip())

        if isinstance(self.capability, str):
            try:
                cap = AICapability(self.capability.lower().strip())
            except ValueError:
                raise ValueError(f"invalid AICapability: {self.capability}")
            object.__setattr__(self, "capability", cap)
        elif not isinstance(self.capability, AICapability):
            raise ValueError("capability must be an AICapability instance")

        if not isinstance(self.timestamp, (int, float)) or self.timestamp < 0:
            raise ValueError("timestamp must be a non-negative number")
        object.__setattr__(self, "timestamp", float(self.timestamp))

        if self.permitted_symbol is not None:
            if not isinstance(self.permitted_symbol, str) or not self.permitted_symbol.strip():
                raise ValueError("permitted_symbol must be a non-empty string if provided")
            object.__setattr__(self, "permitted_symbol", self.permitted_symbol.strip().upper())

        if isinstance(self.permitted_timeline, (list, tuple)):
            clean_timeline = tuple(dict(item) for item in self.permitted_timeline if isinstance(item, dict))
            object.__setattr__(self, "permitted_timeline", clean_timeline)
        else:
            raise ValueError("permitted_timeline must be a list or tuple of dicts")

        if not isinstance(self.is_sanitized, bool):
            raise ValueError("is_sanitized must be a boolean")

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation of the context summary (non-secret)."""
        return {
            "context_id": self.context_id,
            "user_id": self.user_id,
            "capability": self.capability.value,
            "timestamp": self.timestamp,
            "permitted_symbol": self.permitted_symbol,
            "has_permitted_signal": self.permitted_signal is not None,
            "has_permitted_market": self.permitted_market is not None,
            "permitted_timeline_count": len(self.permitted_timeline),
            "has_permitted_health": self.permitted_health is not None,
            "is_sanitized": self.is_sanitized,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class AIRequest:
    """User-initiated request for AI explanation/summarization."""

    request_id: str
    user_id: str
    capability: AICapability
    target_symbol: Optional[str] = None
    prompt_query: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise ValueError("request_id must be a non-empty string")
        object.__setattr__(self, "request_id", self.request_id.strip())

        if not isinstance(self.user_id, str) or not self.user_id.strip():
            raise ValueError("user_id must be a non-empty string")
        object.__setattr__(self, "user_id", self.user_id.strip())

        if isinstance(self.capability, str):
            try:
                cap = AICapability(self.capability.lower().strip())
            except ValueError:
                raise ValueError(f"invalid AICapability: {self.capability}")
            object.__setattr__(self, "capability", cap)
        elif not isinstance(self.capability, AICapability):
            raise ValueError("capability must be an AICapability instance")

        if not isinstance(self.created_at, (int, float)) or self.created_at < 0:
            raise ValueError("created_at must be a non-negative number")
        object.__setattr__(self, "created_at", float(self.created_at))

        if self.target_symbol is not None:
            if not isinstance(self.target_symbol, str) or not self.target_symbol.strip():
                raise ValueError("target_symbol must be a non-empty string if provided")
            object.__setattr__(self, "target_symbol", self.target_symbol.strip().upper())

        if self.prompt_query is not None:
            if not isinstance(self.prompt_query, str):
                raise ValueError("prompt_query must be a string if provided")
            object.__setattr__(self, "prompt_query", self.prompt_query.strip())

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation of the request."""
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "capability": self.capability.value,
            "target_symbol": self.target_symbol,
            "prompt_query": self.prompt_query,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class AIResponse:
    """Response returned by AI Gateway or AI Provider."""

    request_id: str
    status: str
    capability: AICapability
    provider_name: str
    content: str
    created_at: float = field(default_factory=time.time)
    context_summary: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise ValueError("request_id must be a non-empty string")
        object.__setattr__(self, "request_id", self.request_id.strip())

        if not isinstance(self.status, str) or not self.status.strip():
            raise ValueError("status must be a non-empty string")
        object.__setattr__(self, "status", self.status.strip().upper())

        if isinstance(self.capability, str):
            try:
                cap = AICapability(self.capability.lower().strip())
            except ValueError:
                raise ValueError(f"invalid AICapability: {self.capability}")
            object.__setattr__(self, "capability", cap)
        elif not isinstance(self.capability, AICapability):
            raise ValueError("capability must be an AICapability instance")

        if not isinstance(self.provider_name, str) or not self.provider_name.strip():
            raise ValueError("provider_name must be a non-empty string")
        object.__setattr__(self, "provider_name", self.provider_name.strip())

        if not isinstance(self.content, str):
            raise ValueError("content must be a string")
        object.__setattr__(self, "content", self.content.strip())

        if not isinstance(self.created_at, (int, float)) or self.created_at < 0:
            raise ValueError("created_at must be a non-negative number")
        object.__setattr__(self, "created_at", float(self.created_at))

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation of the AI response."""
        return {
            "request_id": self.request_id,
            "status": self.status,
            "capability": self.capability.value,
            "provider_name": self.provider_name,
            "content": self.content,
            "created_at": self.created_at,
            "context_summary": dict(self.context_summary) if self.context_summary else None,
            "error_message": self.error_message,
        }

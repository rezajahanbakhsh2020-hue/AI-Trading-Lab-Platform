"""Provider readiness domain model.

Immutable operational assessment of whether a market data or quote provider
is operationally ready (distinct from provider capabilities and strategy
trade-readiness).
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

PROVIDER_STATUS_READY = "READY"
PROVIDER_STATUS_NOT_READY = "NOT_READY"

VALID_PROVIDER_READINESS_STATUSES = (
    PROVIDER_STATUS_READY,
    PROVIDER_STATUS_NOT_READY,
)


@dataclass(frozen=True)
class ProviderReadiness:
    """Immutable operational readiness verdict for a provider."""

    category: str
    provider_id: str
    status: str
    reason: str
    health: Optional[str] = None
    freshness: Optional[Dict[str, Any]] = None
    capabilities: Dict[str, Any] = None  # type: ignore[assignment]
    metadata: Dict[str, Any] = None  # type: ignore[assignment]
    detail: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.category, str) or not self.category.strip():
            raise ValueError("category must be a non-empty string")
        if not isinstance(self.provider_id, str) or not self.provider_id.strip():
            raise ValueError("provider_id must be a non-empty string")

        status_upper = self.status.upper() if isinstance(self.status, str) else ""
        if status_upper not in VALID_PROVIDER_READINESS_STATUSES:
            raise ValueError(
                f"status must be one of {VALID_PROVIDER_READINESS_STATUSES}, got {self.status!r}"
            )
        object.__setattr__(self, "status", status_upper)

        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")
        object.__setattr__(self, "reason", self.reason.strip())

        if self.capabilities is None:
            object.__setattr__(self, "capabilities", {})
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})

        if self.health is not None:
            if not isinstance(self.health, str) or not self.health.strip():
                raise ValueError("health must be a non-empty string if provided")
            object.__setattr__(self, "health", self.health.strip())

        if self.detail is not None:
            if not isinstance(self.detail, str) or not self.detail.strip():
                raise ValueError("detail must be a non-empty string if provided")
            object.__setattr__(self, "detail", self.detail.strip())

    @property
    def is_ready(self) -> bool:
        """Return True if status is READY."""
        return self.status == PROVIDER_STATUS_READY

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation of ProviderReadiness."""
        return {
            "category": self.category,
            "provider_id": self.provider_id,
            "status": self.status,
            "is_ready": self.is_ready,
            "reason": self.reason,
            "health": self.health,
            "freshness": dict(self.freshness) if isinstance(self.freshness, dict) else self.freshness,
            "capabilities": dict(self.capabilities),
            "metadata": dict(self.metadata),
            "detail": self.detail,
        }

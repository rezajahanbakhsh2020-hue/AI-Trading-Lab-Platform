"""Provider selection domain model (Part 14: Operational Routing).

Immutable result object describing the outcome of a provider selection operation.
Contains selected provider identity, status (SELECTED / NOT_AVAILABLE), reason,
optional preferred provider rejection details, and evaluated readiness objects.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from src.platform.domain.provider_readiness import ProviderReadiness

SELECTION_STATUS_SELECTED = "SELECTED"
SELECTION_STATUS_NOT_AVAILABLE = "NOT_AVAILABLE"

VALID_SELECTION_STATUSES = (
    SELECTION_STATUS_SELECTED,
    SELECTION_STATUS_NOT_AVAILABLE,
)


@dataclass(frozen=True)
class ProviderSelection:
    """Immutable outcome of selecting an operationally ready provider."""

    category: str
    status: str
    reason: str
    selected_provider_id: Optional[str] = None
    preferred_provider_id: Optional[str] = None
    preferred_rejected_reason: Optional[str] = None
    readiness: Optional[ProviderReadiness] = None
    evaluated_readiness: Tuple[ProviderReadiness, ...] = ()
    detail: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.category, str) or not self.category.strip():
            raise ValueError("category must be a non-empty string")

        status_upper = self.status.upper() if isinstance(self.status, str) else ""
        if status_upper not in VALID_SELECTION_STATUSES:
            raise ValueError(
                f"status must be one of {VALID_SELECTION_STATUSES}, got {self.status!r}"
            )
        object.__setattr__(self, "status", status_upper)

        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")
        object.__setattr__(self, "reason", self.reason.strip())

        if self.status == SELECTION_STATUS_SELECTED:
            if not isinstance(self.selected_provider_id, str) or not self.selected_provider_id.strip():
                raise ValueError("selected_provider_id must be a non-empty string when status is SELECTED")
        else:
            if self.selected_provider_id is not None:
                raise ValueError("selected_provider_id must be None when status is NOT_AVAILABLE")

        if self.preferred_provider_id is not None:
            if not isinstance(self.preferred_provider_id, str) or not self.preferred_provider_id.strip():
                raise ValueError("preferred_provider_id must be a non-empty string if provided")
            object.__setattr__(self, "preferred_provider_id", self.preferred_provider_id.strip())

        if self.preferred_rejected_reason is not None:
            if not isinstance(self.preferred_rejected_reason, str) or not self.preferred_rejected_reason.strip():
                raise ValueError("preferred_rejected_reason must be a non-empty string if provided")
            object.__setattr__(self, "preferred_rejected_reason", self.preferred_rejected_reason.strip())

        if self.detail is not None:
            if not isinstance(self.detail, str) or not self.detail.strip():
                raise ValueError("detail must be a non-empty string if provided")
            object.__setattr__(self, "detail", self.detail.strip())

    @property
    def is_selected(self) -> bool:
        """Return True if status is SELECTED."""
        return self.status == SELECTION_STATUS_SELECTED

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation of ProviderSelection."""
        return {
            "category": self.category,
            "status": self.status,
            "is_selected": self.is_selected,
            "reason": self.reason,
            "selected_provider_id": self.selected_provider_id,
            "preferred_provider_id": self.preferred_provider_id,
            "preferred_rejected_reason": self.preferred_rejected_reason,
            "readiness": self.readiness.to_dict() if self.readiness is not None else None,
            "evaluated_readiness": [r.to_dict() for r in self.evaluated_readiness],
            "detail": self.detail,
        }

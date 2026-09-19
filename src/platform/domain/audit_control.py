"""Operational Control Plane & Audit domain models for AI-Trading-Lab-Platform.

Provides domain objects for lifecycle tracking, audit log events, operational health,
and correlation across all platform subsystems without exposing proprietary strategy logic or secrets.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AuditCategory(str, Enum):
    """Subsystem categories for operational audit tracking."""

    SIGNAL_INTAKE = "SIGNAL_INTAKE"
    BACKTEST_ASSESSMENT = "BACKTEST_ASSESSMENT"
    STRATEGY_VALIDATION = "STRATEGY_VALIDATION"
    AUTONOMOUS_AUTHORIZATION = "AUTONOMOUS_AUTHORIZATION"
    ORDER_INTENT = "ORDER_INTENT"
    NOTIFICATION_DISPATCH = "NOTIFICATION_DISPATCH"
    PROVIDER_HEALTH = "PROVIDER_HEALTH"
    SECURITY_AUTHORIZATION = "SECURITY_AUTHORIZATION"
    OPERATIONAL_SYSTEM = "OPERATIONAL_SYSTEM"


class OperationalLifecycleState(str, Enum):
    """Lifecycle states of operational actions across the platform."""

    INITIATED = "INITIATED"
    PROCESSING = "PROCESSING"
    VALIDATED = "VALIDATED"
    AUTHORIZED = "AUTHORIZED"
    STAGED = "STAGED"
    DISPATCHED = "DISPATCHED"
    COMPLETED = "COMPLETED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class AuditEventSeverity(str, Enum):
    """Severity levels for audit events."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class AuditEvent:
    """Represents a single sanitized, authorized operational audit event."""

    event_id: str
    timestamp: float
    user_id: str
    category: AuditCategory
    event_type: str
    lifecycle_state: OperationalLifecycleState
    action: str
    outcome: str
    severity: AuditEventSeverity = AuditEventSeverity.INFO
    resource_id: Optional[str] = None
    correlation_id: Optional[str] = None
    details: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit event to dictionary representation."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "category": self.category.value if isinstance(self.category, AuditCategory) else str(self.category),
            "event_type": self.event_type,
            "lifecycle_state": self.lifecycle_state.value if isinstance(self.lifecycle_state, OperationalLifecycleState) else str(self.lifecycle_state),
            "action": self.action,
            "outcome": self.outcome,
            "severity": self.severity.value if isinstance(self.severity, AuditEventSeverity) else str(self.severity),
            "resource_id": self.resource_id,
            "correlation_id": self.correlation_id,
            "details": self.details,
            "metadata": self.metadata,
        }


@dataclass
class AuditQueryFilter:
    """Filter parameters for querying audit events."""

    user_id: Optional[str] = None
    category: Optional[AuditCategory] = None
    lifecycle_state: Optional[OperationalLifecycleState] = None
    outcome: Optional[str] = None
    severity: Optional[AuditEventSeverity] = None
    correlation_id: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    limit: int = 100


@dataclass
class OperationalFailureRecord:
    """Canonical representation of platform operational failures and incidents."""

    failure_id: str
    timestamp: float
    correlation_id: str
    component: str
    error_type: str
    severity: AuditEventSeverity
    retryable: bool
    message: str
    diagnostic_details: Optional[str] = None
    user_id: str = "system"

    def to_dict(self) -> Dict[str, Any]:
        """Convert failure record to dictionary representation."""
        return {
            "failure_id": self.failure_id,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "component": self.component,
            "error_type": self.error_type,
            "severity": self.severity.value if isinstance(self.severity, AuditEventSeverity) else str(self.severity),
            "retryable": self.retryable,
            "message": self.message,
            "diagnostic_details": self.diagnostic_details,
            "user_id": self.user_id,
        }


@dataclass
class AuditControlSummary:
    """Summary metrics of operational control plane events."""

    total_events: int
    events_by_category: Dict[str, int]
    events_by_severity: Dict[str, int]
    events_by_lifecycle: Dict[str, int]
    failed_events_count: int
    degraded_events_count: int
    last_event_timestamp: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary representation."""
        return {
            "total_events": self.total_events,
            "events_by_category": self.events_by_category,
            "events_by_severity": self.events_by_severity,
            "events_by_lifecycle": self.events_by_lifecycle,
            "failed_events_count": self.failed_events_count,
            "degraded_events_count": self.degraded_events_count,
            "last_event_timestamp": self.last_event_timestamp,
        }

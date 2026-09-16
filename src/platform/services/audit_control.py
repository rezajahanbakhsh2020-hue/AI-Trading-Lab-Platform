"""Platform Operational Control Plane and Audit Service.

Provides secure, authorization-enforced, sanitized logging, lifecycle tracking,
and query capabilities for all platform operational events.
"""

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from src.platform.domain.audit_control import (
    AuditCategory,
    AuditControlSummary,
    AuditEvent,
    AuditEventSeverity,
    AuditQueryFilter,
    OperationalLifecycleState,
)
from src.platform.domain.security import Permission
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.security import SecretSanitizer, SecurityBoundaryService


class PlatformAuditControlService:
    """Service providing operational control plane monitoring and audit tracking."""

    def __init__(
        self,
        security_boundary: Optional[SecurityBoundaryService] = None,
        max_events: int = 2000,
    ) -> None:
        self.security_boundary = security_boundary or SecurityBoundaryService()
        self._max_events = max(100, max_events)
        self._events: List[AuditEvent] = []
        self._seed_initial_system_events()

    def _seed_initial_system_events(self) -> None:
        """Seed baseline system operational events for platform lifecycle tracking."""
        now = time.time()
        initial_events = [
            AuditEvent(
                event_id=str(uuid.uuid4()),
                timestamp=now - 300,
                user_id="system",
                category=AuditCategory.OPERATIONAL_SYSTEM,
                event_type="SYSTEM_INITIALIZED",
                lifecycle_state=OperationalLifecycleState.COMPLETED,
                action="INITIALIZE_PLATFORM",
                outcome="SUCCESS",
                severity=AuditEventSeverity.INFO,
                resource_id="platform_core",
                correlation_id="sys-init-001",
                details="Platform operational control plane initialized safely.",
                metadata={"version": "1.0.0", "status": "HEALTHY"},
            ),
            AuditEvent(
                event_id=str(uuid.uuid4()),
                timestamp=now - 200,
                user_id="system",
                category=AuditCategory.PROVIDER_HEALTH,
                event_type="PROVIDER_CHECK",
                lifecycle_state=OperationalLifecycleState.COMPLETED,
                action="CHECK_READINESS",
                outcome="SUCCESS",
                severity=AuditEventSeverity.INFO,
                resource_id="project1_lab_adapter",
                correlation_id="sys-prov-002",
                details="Lab artifact provider adapter verified and online.",
                metadata={"provider": "Project1LabArtifactAdapter", "status": "READY"},
            ),
        ]
        self._events.extend(initial_events)

    def record_event(
        self,
        user_id: str,
        category: AuditCategory,
        event_type: str,
        lifecycle_state: OperationalLifecycleState,
        action: str,
        outcome: str,
        severity: AuditEventSeverity = AuditEventSeverity.INFO,
        resource_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        details: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
    ) -> AuditEvent:
        """Record a sanitized operational audit event."""
        clean_user_id = str(user_id or "anonymous").strip()
        clean_action = SecretSanitizer.sanitize_string(action or "UNKNOWN")
        clean_outcome = SecretSanitizer.sanitize_string(outcome or "UNKNOWN")
        clean_details = SecretSanitizer.sanitize_string(details) if details else None

        # Sanitize metadata to remove any secret or strategy logic keys
        sanitized_meta = SecretSanitizer.sanitize_data(metadata or {})
        if isinstance(sanitized_meta, dict):
            # Strip extra proprietary keys if present
            protected_keys = {"indicator_logic", "strategy_params", "sensitive_parameters", "lab_secrets", "secrets"}
            sanitized_meta = {k: v for k, v in sanitized_meta.items() if str(k).lower() not in protected_keys}
        else:
            sanitized_meta = {}

        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=float(timestamp if timestamp is not None else time.time()),
            user_id=clean_user_id,
            category=category,
            event_type=str(event_type).upper(),
            lifecycle_state=lifecycle_state,
            action=clean_action,
            outcome=clean_outcome,
            severity=severity,
            resource_id=resource_id,
            correlation_id=correlation_id,
            details=clean_details,
            metadata=sanitized_meta,
        )

        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events.pop(0)

        return event

    def query_events(
        self,
        user: Optional[UserAuthorization],
        filter_params: Optional[AuditQueryFilter] = None,
    ) -> Tuple[bool, str, List[AuditEvent]]:
        """Query operational audit events with security authorization and user isolation."""
        # Enforce server-side authorization check
        authorized, reason = self.security_boundary.authorize(
            user=user,
            resource="signals", # Standard resource check or permitted user
            action="read",
        )
        if not authorized or user is None:
            return False, f"Unauthorized: {reason}", []

        filters = filter_params or AuditQueryFilter()
        is_admin = user.is_admin

        result: List[AuditEvent] = []
        for e in self._events:
            # Multi-tenant / User isolation: non-admins only see system events or their own events
            if not is_admin and e.user_id not in ("system", user.user_id):
                continue

            # Target user filter if explicitly requested
            if filters.user_id and e.user_id != filters.user_id.strip():
                # Non-admin requesting another user's events is blocked by user isolation
                if not is_admin and filters.user_id.strip() != user.user_id:
                    continue
                if is_admin and e.user_id != filters.user_id.strip():
                    continue

            # Category filter
            if filters.category and e.category != filters.category:
                continue

            # Lifecycle state filter
            if filters.lifecycle_state and e.lifecycle_state != filters.lifecycle_state:
                continue

            # Severity filter
            if filters.severity and e.severity != filters.severity:
                continue

            # Outcome filter
            if filters.outcome and e.outcome.upper() != filters.outcome.strip().upper():
                continue

            # Correlation ID filter
            if filters.correlation_id and e.correlation_id != filters.correlation_id.strip():
                continue

            # Time range filter
            if filters.start_time is not None and e.timestamp < filters.start_time:
                continue
            if filters.end_time is not None and e.timestamp > filters.end_time:
                continue

            result.append(e)

        # Sort descending by timestamp
        result.sort(key=lambda x: x.timestamp, reverse=True)
        limit = max(1, filters.limit)
        return True, "Events retrieved successfully.", result[:limit]

    def get_control_summary(
        self, user: Optional[UserAuthorization]
    ) -> Tuple[bool, str, Optional[AuditControlSummary]]:
        """Compute operational control plane summary metrics for authorized user."""
        success, msg, events = self.query_events(user, AuditQueryFilter(limit=1000))
        if not success:
            return False, msg, None

        events_by_category: Dict[str, int] = {}
        events_by_severity: Dict[str, int] = {}
        events_by_lifecycle: Dict[str, int] = {}
        failed_count = 0
        degraded_count = 0
        latest_ts: Optional[float] = None

        for e in events:
            cat_str = e.category.value if isinstance(e.category, AuditCategory) else str(e.category)
            sev_str = e.severity.value if isinstance(e.severity, AuditEventSeverity) else str(e.severity)
            life_str = e.lifecycle_state.value if isinstance(e.lifecycle_state, OperationalLifecycleState) else str(e.lifecycle_state)

            events_by_category[cat_str] = events_by_category.get(cat_str, 0) + 1
            events_by_severity[sev_str] = events_by_severity.get(sev_str, 0) + 1
            events_by_lifecycle[life_str] = events_by_lifecycle.get(life_str, 0) + 1

            if e.lifecycle_state == OperationalLifecycleState.FAILED or e.outcome == "FAILURE":
                failed_count += 1
            if e.lifecycle_state == OperationalLifecycleState.DEGRADED or e.outcome == "DEGRADED":
                degraded_count += 1

            if latest_ts is None or e.timestamp > latest_ts:
                latest_ts = e.timestamp

        summary = AuditControlSummary(
            total_events=len(events),
            events_by_category=events_by_category,
            events_by_severity=events_by_severity,
            events_by_lifecycle=events_by_lifecycle,
            failed_events_count=failed_count,
            degraded_events_count=degraded_count,
            last_event_timestamp=latest_ts,
        )

        return True, "Summary generated successfully.", summary

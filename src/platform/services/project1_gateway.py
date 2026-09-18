"""Project 1 Integration Gateway Application Service.

Hexagonal application service enforcing authenticated, version-validated,
user-isolated, replay-protected, and auditable ingestion and lifecycle handling
for Project 1 outputs.

Rules:
- NEVER calculates or modifies strategy logic, Entry, SL, TP, trailing stops, or trading rules.
- Strictly validates incoming contract schema and contract version.
- Enforces user isolation, RBAC, least privilege, and audit control plane logging.
"""

import time
import uuid
from typing import Any, Dict, List, Optional

from src.platform.adapters.project1_repository import (
    FileBackedProject1IntegrationRepository,
    Project1IntegrationRepositoryPort,
)
from src.platform.domain.audit_control import AuditCategory, AuditEventSeverity, OperationalLifecycleState
from src.platform.domain.project1_contract import (
    get_project1_contract_capabilities,
    validate_project1_contract_payload,
)

from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.security import SecretSanitizer, SecurityBoundaryService


class Project1IntegrationGatewayService:
    """Application service managing Project 1 integration boundary."""

    def __init__(
        self,
        repository: Optional[Project1IntegrationRepositoryPort] = None,
        security_boundary: Optional[SecurityBoundaryService] = None,
        audit_control: Optional[PlatformAuditControlService] = None,
    ) -> None:
        self._repo = repository or FileBackedProject1IntegrationRepository()
        self._security = security_boundary or SecurityBoundaryService()
        self._audit = audit_control or PlatformAuditControlService(security_boundary=self._security)

    def get_capabilities(self, user: Optional[UserAuthorization] = None) -> Dict[str, Any]:
        """Return contract capabilities discovery payload."""
        caps = get_project1_contract_capabilities()

        # Audit log discovery
        self._audit.record_event(
            user_id=user.user_id if user else "guest",
            category=AuditCategory.OPERATIONAL_SYSTEM,
            event_type="CONTRACT_CAPABILITIES_DISCOVERED",
            lifecycle_state=OperationalLifecycleState.COMPLETED,
            action="DISCOVER_PROJECT1_CONTRACT",
            outcome="SUCCESS",
            severity=AuditEventSeverity.INFO,
            resource_id="project1_gateway",
            details="Project 1 integration gateway capabilities queried.",
            metadata=SecretSanitizer.sanitize_data(caps),
        )

        return {
            "success": True,
            "capabilities": caps,
        }

    def ingest_signal_payload(
        self,
        user: Optional[UserAuthorization],
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate, authorize, scope, check replay, and ingest Project 1 signal contract payload."""

        # 1. Authentication Check
        if user is None:
            return {
                "success": False,
                "error_code": "UNAUTHENTICATED",
                "message": "Authentication required for Project 1 output ingestion.",
            }

        # 2. RBAC Authorization Check
        allowed, reason = self._security.authorize(user, "signals", action="write")
        if not allowed:
            self._audit.record_event(
                user_id=user.user_id,
                category=AuditCategory.SECURITY_AUTHORIZATION,
                event_type="INGESTION_UNAUTHORIZED",
                lifecycle_state=OperationalLifecycleState.REJECTED,
                action="INTAKE_PROJECT1_SIGNAL",
                outcome="FAILURE",
                severity=AuditEventSeverity.WARNING,
                resource_id="project1_gateway",
                details=f"Project 1 output ingestion denied: {reason}",
            )
            return {
                "success": False,
                "error_code": "UNAUTHORIZED",
                "message": f"Access denied: {reason}",
            }

        # 3. Schema & Version Contract Validation
        val_res = validate_project1_contract_payload(payload)
        if not val_res.is_valid:
            err_msg = "; ".join(val_res.errors)
            is_version_err = any("Unsupported contract version" in e for e in val_res.errors)
            err_code = "UNSUPPORTED_CONTRACT_VERSION" if is_version_err else "INVALID_CONTRACT_SCHEMA"

            self._audit.record_event(
                user_id=user.user_id,
                category=AuditCategory.SIGNAL_INTAKE,
                event_type="INGESTION_CONTRACT_REJECTED",
                lifecycle_state=OperationalLifecycleState.REJECTED,
                action="INTAKE_PROJECT1_SIGNAL",
                outcome="FAILURE",
                severity=AuditEventSeverity.WARNING,
                resource_id="project1_gateway",
                details=f"Payload rejected at boundary: {err_msg}",
            )
            return {
                "success": False,
                "error_code": err_code,
                "message": f"Contract validation failed: {err_msg}",
                "errors": list(val_res.errors),
            }

        sanitized = dict(val_res.sanitized_payload or {})

        # 4. Customer Isolation & IDOR Check
        payload_user_id = sanitized.get("user_id")
        if payload_user_id and payload_user_id != user.user_id and not user.is_admin:
            self._audit.record_event(
                user_id=user.user_id,
                category=AuditCategory.SECURITY_AUTHORIZATION,
                event_type="IDOR_INGESTION_ATTEMPT",
                lifecycle_state=OperationalLifecycleState.REJECTED,
                action="INTAKE_PROJECT1_SIGNAL",
                outcome="FAILURE",
                severity=AuditEventSeverity.ERROR,
                resource_id=payload_user_id,
                details=f"User {user.user_id} attempted signal ingestion targeting {payload_user_id}",
            )
            return {
                "success": False,
                "error_code": "FORBIDDEN_USER_MISMATCH",
                "message": "Cannot ingest signal for another user identity.",
            }

        sanitized["user_id"] = user.user_id
        if not sanitized.get("tenant_id"):
            sanitized["tenant_id"] = f"tenant_{user.user_id}"

        # 5. Correlation ID Generation or Propagation
        correlation_id = sanitized.get("correlation_id")
        if not correlation_id:
            correlation_id = f"p1_corr_{int(time.time())}_{sanitized['signal_id']}"
            sanitized["correlation_id"] = correlation_id

        # 6. Replay Protection & Idempotency Check
        if self._repo.is_duplicate_request(signal_id=sanitized["signal_id"], user_id=user.user_id):
            existing = self._repo.get_record_by_id(sanitized["integration_id"], user_id=user.user_id)
            self._audit.record_event(
                user_id=user.user_id,
                category=AuditCategory.SIGNAL_INTAKE,
                event_type="SIGNAL_REPLAY_DETECTED",
                lifecycle_state=OperationalLifecycleState.COMPLETED,
                action="INTAKE_PROJECT1_SIGNAL",
                outcome="SUCCESS",
                severity=AuditEventSeverity.INFO,
                resource_id=sanitized["signal_id"],
                correlation_id=correlation_id,
                details="Idempotent replay detected. Returned existing record without duplicate processing.",
            )
            return {
                "success": True,
                "status": "DUPLICATE_ACCEPTED",
                "message": "Signal ingestion accepted (idempotent replay).",
                "record": SecretSanitizer.sanitize_data(existing) if existing else sanitized,
                "correlation_id": correlation_id,
            }

        # 7. Lifecycle state initialization & Persistence
        if "lifecycle_state" not in sanitized:
            sanitized["lifecycle_state"] = "STAGED"

        saved_rec = self._repo.save_record(sanitized)

        # 8. Audit Logging
        self._audit.record_event(
            user_id=user.user_id,
            category=AuditCategory.SIGNAL_INTAKE,
            event_type="SIGNAL_INGESTED",
            lifecycle_state=OperationalLifecycleState.STAGED,
            action="INTAKE_PROJECT1_SIGNAL",
            outcome="SUCCESS",
            severity=AuditEventSeverity.INFO,
            resource_id=sanitized["signal_id"],
            correlation_id=correlation_id,
            details=f"Project 1 signal {sanitized['signal_id']} ({sanitized.get('symbol')}) ingested safely.",
            metadata={
                "symbol": sanitized.get("symbol"),
                "signal_type": sanitized.get("signal_type"),
                "strategy_name": sanitized.get("strategy_name"),
                "contract_version": sanitized.get("contract_version"),
            },
        )

        return {
            "success": True,
            "status": "INGESTED",
            "message": "Project 1 signal contract payload successfully validated and ingested.",
            "record": SecretSanitizer.sanitize_data(saved_rec),
            "correlation_id": correlation_id,
        }

    def update_lifecycle(
        self,
        user: Optional[UserAuthorization],
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update lifecycle state of an existing ingested signal record."""
        if user is None:
            return {
                "success": False,
                "error_code": "UNAUTHENTICATED",
                "message": "Authentication required for lifecycle transition.",
            }

        allowed, reason = self._security.authorize(user, "signals", action="write")
        if not allowed:
            return {
                "success": False,
                "error_code": "UNAUTHORIZED",
                "message": f"Access denied: {reason}",
            }

        if not isinstance(payload, dict):
            return {
                "success": False,
                "error_code": "INVALID_PAYLOAD",
                "message": "Payload must be a JSON dictionary.",
            }

        signal_id = payload.get("signal_id")
        lifecycle_state = payload.get("lifecycle_state")
        reason_str = payload.get("reason")

        if not signal_id or not isinstance(signal_id, str):
            return {
                "success": False,
                "error_code": "INVALID_SIGNAL_ID",
                "message": "signal_id is required.",
            }

        if not lifecycle_state or not isinstance(lifecycle_state, str):
            return {
                "success": False,
                "error_code": "INVALID_LIFECYCLE_STATE",
                "message": "lifecycle_state is required.",
            }

        ls_upper = lifecycle_state.strip().upper()
        if ls_upper not in ("STAGED", "ACTIVE", "UPDATED", "CANCELLED", "EXPIRED", "REJECTED", "EXECUTED"):
            return {
                "success": False,
                "error_code": "UNSUPPORTED_LIFECYCLE_STATE",
                "message": f"Unsupported lifecycle state: {lifecycle_state}",
            }

        success = self._repo.update_lifecycle_state(
            signal_id=signal_id.strip(),
            lifecycle_state=ls_upper,
            reason=reason_str,
            user_id=None if user.is_admin else user.user_id,
        )

        if not success:
            return {
                "success": False,
                "error_code": "RECORD_NOT_FOUND",
                "message": f"No signal record found with signal_id '{signal_id}' for current user.",
            }

        corr_id = payload.get("correlation_id") or f"p1_lifecycle_{int(time.time())}"

        self._audit.record_event(
            user_id=user.user_id,
            category=AuditCategory.SIGNAL_INTAKE,
            event_type="LIFECYCLE_UPDATED",
            lifecycle_state=OperationalLifecycleState.COMPLETED,
            action="UPDATE_SIGNAL_LIFECYCLE",
            outcome="SUCCESS",
            severity=AuditEventSeverity.INFO,
            resource_id=signal_id,
            correlation_id=corr_id,
            details=f"Signal {signal_id} lifecycle updated to {ls_upper}.",
        )

        return {
            "success": True,
            "signal_id": signal_id,
            "lifecycle_state": ls_upper,
            "message": f"Signal {signal_id} lifecycle state updated to {ls_upper}.",
            "correlation_id": corr_id,
        }

    def list_records(
        self,
        user: Optional[UserAuthorization],
        symbol: Optional[str] = None,
        lifecycle_state: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """List integration records for the authorized user."""
        if user is None:
            return {
                "success": False,
                "error_code": "UNAUTHENTICATED",
                "records": [],
                "message": "Authentication required.",
            }

        allowed, reason = self._security.authorize(user, "signals", action="read")
        if not allowed:
            return {
                "success": False,
                "error_code": "UNAUTHORIZED",
                "records": [],
                "message": f"Access denied: {reason}",
            }

        effective_user_id = None if user.is_admin else user.user_id
        records = self._repo.list_records_for_user(
            user_id=effective_user_id,
            symbol=symbol,
            lifecycle_state=lifecycle_state,
            limit=limit,
        )

        sanitized_records = [SecretSanitizer.sanitize_data(r) for r in records]

        return {
            "success": True,
            "records": sanitized_records,
            "count": len(sanitized_records),
        }

"""Project 1 Integration Gateway Application Service.

Hexagonal application service enforcing authenticated, version-validated,
user-isolated, replay-protected, and auditable ingestion and lifecycle handling
for Project 1 outputs.

Rules:
- NEVER calculates or modifies strategy logic, Entry, SL, TP, trailing stops, or trading rules.
- Strictly validates incoming contract schema and contract version.
- Enforces user isolation, RBAC, least privilege, and audit control plane logging.
"""

import base64
import json
import math
import time
import uuid
from typing import Any, Dict, List, Optional

from src.platform.adapters.project1_repository import (
    FileBackedProject1IntegrationRepository,
    Project1IntegrationRepositoryPort,
    RepositoryStatus,
)
from src.platform.domain.audit_control import AuditCategory, AuditEventSeverity, OperationalLifecycleState
from src.platform.domain.project1_contract import (
    get_project1_contract_capabilities,
    validate_project1_contract_payload,
)

from src.platform.domain.user_authorization import UserAuthorization
from src.platform.domain.notification import NotificationCategory, NotificationEvent, NotificationSeverity
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.notification import NotificationService
from src.platform.services.security import SecretSanitizer, SecurityBoundaryService


class Project1IntegrationGatewayService:
    """Application service managing Project 1 integration boundary."""

    def __init__(
        self,
        repository: Optional[Project1IntegrationRepositoryPort] = None,
        security_boundary: Optional[SecurityBoundaryService] = None,
        audit_control: Optional[PlatformAuditControlService] = None,
        notification_service: Optional[NotificationService] = None,
        service_key: Optional[str] = None,
    ) -> None:
        self._security = security_boundary or SecurityBoundaryService()
        self._audit = audit_control or PlatformAuditControlService(security_boundary=self._security)
        self._repo = repository or FileBackedProject1IntegrationRepository(audit_control=self._audit)
        self._notif_svc = notification_service
        self._service_key = service_key or "dev_project1_service_key_2026"

    def resolve_authoritative_publication(
        self,
        user: Optional[UserAuthorization],
        publication_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Resolve authoritative Project 1 publication record for canonical OrderIntent creation.

        Strictly uses publication_id selector and enforces user/tenant isolation and RBAC authorization.
        """
        if user is None:
            return None

        allowed, _ = self._security.authorize(user, "signals", action="read")
        if not allowed:
            return None

        if not isinstance(publication_id, str) or not publication_id.strip():
            return None

        clean_pub_id = publication_id.strip()
        effective_user_id = None if user.is_admin else user.user_id

        record = self._repo.find_authoritative_record(
            {"publication_id": clean_pub_id},
            user_id=effective_user_id,
        )

        if not record:
            return None

        if record.get("publication_id") != clean_pub_id:
            return None

        return SecretSanitizer.sanitize_data(record)

    def authenticate_service_credential(self, provided_credential: Optional[str]) -> bool:
        """Verify service-to-service credential supplied in Authorization or X-API-Key header."""
        if not provided_credential or not isinstance(provided_credential, str):
            return False
        import hmac
        return hmac.compare_digest(provided_credential.strip(), self._service_key)

    def get_capabilities(self, user: Optional[UserAuthorization] = None) -> Dict[str, Any]:
        """Return contract capabilities discovery payload."""
        caps = get_project1_contract_capabilities()

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
        raw_payload = payload if isinstance(payload, dict) else {}
        corr_id = raw_payload.get("correlation_id") or f"p1_corr_{int(time.time()*1000)}"

        # 1. Authentication Check
        if user is None:
            self._audit.record_failure(
                component="Project1IntegrationGateway",
                error_type="UNAUTHENTICATED_INGESTION_ATTEMPT",
                message="Authentication required for Project 1 output ingestion.",
                severity=AuditEventSeverity.WARNING,
                correlation_id=corr_id,
                user_id="anonymous",
            )
            return {
                "success": False,
                "error_code": "UNAUTHENTICATED",
                "message": "Authentication required for Project 1 output ingestion.",
                "correlation_id": corr_id,
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
                correlation_id=corr_id,
                details=f"Project 1 output ingestion denied: {reason}",
            )
            self._audit.record_failure(
                component="Project1IntegrationGateway",
                error_type="UNAUTHORIZED_INGESTION_ATTEMPT",
                message=f"Access denied: {reason}",
                severity=AuditEventSeverity.WARNING,
                correlation_id=corr_id,
                user_id=user.user_id,
            )
            return {
                "success": False,
                "error_code": "UNAUTHORIZED",
                "message": f"Access denied: {reason}",
                "correlation_id": corr_id,
            }

        # 3. Schema & Version Contract Validation
        val_res = validate_project1_contract_payload(raw_payload)
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
                correlation_id=corr_id,
                details=f"Payload rejected at boundary: {err_msg}",
            )
            self._audit.record_failure(
                component="Project1IntegrationGateway",
                error_type=err_code,
                message=f"Contract validation failed: {err_msg}",
                severity=AuditEventSeverity.WARNING,
                correlation_id=corr_id,
                user_id=user.user_id,
            )
            return {
                "success": False,
                "error_code": err_code,
                "message": f"Contract validation failed: {err_msg}",
                "errors": list(val_res.errors),
                "correlation_id": corr_id,
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
                correlation_id=corr_id,
                details=f"User {user.user_id} attempted signal ingestion targeting {payload_user_id}",
            )
            self._audit.record_failure(
                component="Project1IntegrationGateway",
                error_type="FORBIDDEN_USER_MISMATCH",
                message=f"User {user.user_id} attempted signal ingestion targeting {payload_user_id}",
                severity=AuditEventSeverity.ERROR,
                correlation_id=corr_id,
                user_id=user.user_id,
            )
            return {
                "success": False,
                "error_code": "FORBIDDEN_USER_MISMATCH",
                "message": "Cannot ingest signal for another user identity.",
                "correlation_id": corr_id,
            }

        sanitized["user_id"] = user.user_id
        if not sanitized.get("tenant_id"):
            sanitized["tenant_id"] = f"tenant_{user.user_id}"

        raw_int_id = sanitized.get("integration_id") or f"p1_{sanitized.get('publication_id')}_{sanitized.get('event_id')}"
        if not raw_int_id.startswith(f"{user.user_id}:"):
            sanitized["integration_id"] = f"{user.user_id}:{raw_int_id}"

        meta = sanitized.get("metadata")
        if not isinstance(meta, dict):
            meta = {}
        sanitized["metadata"] = meta

        # 5. Correlation ID Generation or Propagation
        correlation_id = sanitized.get("correlation_id")
        if not correlation_id:
            correlation_id = f"p1_corr_{int(time.time())}_{sanitized['signal_id']}"
            sanitized["correlation_id"] = correlation_id

        if "lifecycle_state" not in sanitized:
            sanitized["lifecycle_state"] = "STAGED"

        # 6. Atomic Ingest & State Resolution
        ingest_res = self._repo.ingest_authoritative_record(sanitized, user_id=user.user_id)
        ingest_status = ingest_res.get("status")
        rec_payload = ingest_res.get("record") or {}

        if ingest_status == RepositoryStatus.DUPLICATE_ACCEPTED:
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
                "record": SecretSanitizer.sanitize_data(rec_payload),
                "correlation_id": correlation_id,
            }

        elif ingest_status == RepositoryStatus.DURABILITY_UNCERTAIN:
            self._audit.record_event(
                user_id=user.user_id,
                category=AuditCategory.SIGNAL_INTAKE,
                event_type="INGESTION_DURABILITY_UNCERTAIN",
                lifecycle_state=OperationalLifecycleState.STAGED,
                action="INTAKE_PROJECT1_SIGNAL",
                outcome="DEGRADED",
                severity=AuditEventSeverity.WARNING,
                resource_id=sanitized["signal_id"],
                correlation_id=correlation_id,
                details="Signal committed to target storage file, but parent directory durability was uncertain.",
            )
            return {
                "success": False,
                "status": "DURABILITY_UNCERTAIN",
                "error_code": "DURABILITY_UNCERTAIN",
                "message": "Signal payload committed to file, but directory durability was uncertain.",
                "record": SecretSanitizer.sanitize_data(rec_payload),
                "correlation_id": correlation_id,
            }

        elif ingest_status in (
            RepositoryStatus.INTEGRITY_CONFLICT,
            RepositoryStatus.IDENTITY_AMBIGUOUS,
            RepositoryStatus.STORAGE_CORRUPT,
            RepositoryStatus.STORAGE_UNAVAILABLE,
            RepositoryStatus.PERSISTENCE_FAILURE,
            RepositoryStatus.IDENTITY_COLLISION,
            RepositoryStatus.ABSENT,
        ):
            err_code = str(ingest_status.value)
            msg = ingest_res.get("message", "Ingestion rejected due to repository constraint.")

            self._audit.record_event(
                user_id=user.user_id,
                category=AuditCategory.SIGNAL_INTAKE,
                event_type=f"INGESTION_{err_code}_REJECTED",
                lifecycle_state=OperationalLifecycleState.REJECTED,
                action="INTAKE_PROJECT1_SIGNAL",
                outcome="FAILURE",
                severity=AuditEventSeverity.ERROR,
                resource_id=sanitized["signal_id"],
                correlation_id=correlation_id,
                details=f"Ingestion rejected: {msg}",
            )
            self._audit.record_failure(
                component="Project1IntegrationGateway",
                error_type=err_code,
                message=msg,
                severity=AuditEventSeverity.ERROR,
                correlation_id=correlation_id,
                user_id=user.user_id,
            )
            return {
                "success": False,
                "error_code": err_code,
                "message": msg,
                "correlation_id": correlation_id,
            }

        elif ingest_status != RepositoryStatus.CREATED:
            err_code = "UNKNOWN_REPOSITORY_STATUS"
            msg = f"Unrecognized repository status received: {ingest_status}"

            self._audit.record_event(
                user_id=user.user_id,
                category=AuditCategory.SIGNAL_INTAKE,
                event_type="INGESTION_UNKNOWN_STATUS_REJECTED",
                lifecycle_state=OperationalLifecycleState.REJECTED,
                action="INTAKE_PROJECT1_SIGNAL",
                outcome="FAILURE",
                severity=AuditEventSeverity.ERROR,
                resource_id=sanitized["signal_id"],
                correlation_id=correlation_id,
                details=msg,
            )
            self._audit.record_failure(
                component="Project1IntegrationGateway",
                error_type=err_code,
                message=msg,
                severity=AuditEventSeverity.ERROR,
                correlation_id=correlation_id,
                user_id=user.user_id,
            )
            return {
                "success": False,
                "error_code": err_code,
                "message": msg,
                "correlation_id": correlation_id,
            }

        # Status is CREATED
        saved_rec = rec_payload

        # 7. Audit Logging
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

        # 8. User-scoped Notification Creation
        if self._notif_svc is not None:
            evt = NotificationEvent(
                event_id=f"p1_ingest_{sanitized['signal_id']}",
                event_type="PROJECT1_SIGNAL_INGESTED",
                category=NotificationCategory.PROJECT1_INTEGRATION,
                severity=NotificationSeverity.INFO,
                title=f"Project 1 Signal Ingested: {sanitized.get('symbol')} ({sanitized.get('signal_type', '').upper()})",
                message=f"Signal {sanitized['signal_id']} for {sanitized.get('symbol')} received from Project 1 (contract v{sanitized.get('contract_version', '1.0')}).",
                timestamp=time.time(),
                target_user_id=user.user_id,
                payload={
                    "signal_id": sanitized["signal_id"],
                    "symbol": sanitized.get("symbol"),
                    "signal_type": sanitized.get("signal_type"),
                    "strategy_name": sanitized.get("strategy_name"),
                },
                version=str(sanitized.get("contract_version", "1.0")),
                source="project1_gateway",
                correlation_id=correlation_id,
                status="INGESTED",
            )
            self._notif_svc.create_notification_from_event(evt)

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
        raw_payload = payload if isinstance(payload, dict) else {}
        corr_id = raw_payload.get("correlation_id") or f"p1_lifecycle_{int(time.time()*1000)}"

        if user is None:
            return {
                "success": False,
                "error_code": "UNAUTHENTICATED",
                "message": "Authentication required for lifecycle transition.",
                "correlation_id": corr_id,
            }

        allowed, reason = self._security.authorize(user, "signals", action="write")
        if not allowed:
            return {
                "success": False,
                "error_code": "UNAUTHORIZED",
                "message": f"Access denied: {reason}",
                "correlation_id": corr_id,
            }

        if not isinstance(payload, dict):
            return {
                "success": False,
                "error_code": "INVALID_PAYLOAD",
                "message": "Payload must be a JSON dictionary.",
                "correlation_id": corr_id,
            }

        signal_id = payload.get("signal_id")
        lifecycle_state = payload.get("lifecycle_state")
        reason_str = payload.get("reason")

        if not signal_id or not isinstance(signal_id, str):
            return {
                "success": False,
                "error_code": "INVALID_SIGNAL_ID",
                "message": "signal_id is required.",
                "correlation_id": corr_id,
            }

        if not lifecycle_state or not isinstance(lifecycle_state, str):
            return {
                "success": False,
                "error_code": "INVALID_LIFECYCLE_STATE",
                "message": "lifecycle_state is required.",
                "correlation_id": corr_id,
            }

        ls_upper = lifecycle_state.strip().upper()
        if ls_upper not in ("STAGED", "ACTIVE", "UPDATED", "CANCELLED", "EXPIRED", "REJECTED", "EXECUTED"):
            return {
                "success": False,
                "error_code": "UNSUPPORTED_LIFECYCLE_STATE",
                "message": f"Unsupported lifecycle state: {lifecycle_state}",
                "correlation_id": corr_id,
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
                "correlation_id": corr_id,
            }

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

        if self._notif_svc is not None:
            evt = NotificationEvent(
                event_id=f"p1_lifecycle_{signal_id}_{int(time.time())}",
                event_type="SIGNAL_LIFECYCLE_UPDATED",
                category=NotificationCategory.SIGNAL_LIFECYCLE,
                severity=NotificationSeverity.INFO,
                title=f"Signal Lifecycle Updated: {signal_id}",
                message=f"Signal {signal_id} lifecycle state changed to {ls_upper}.",
                timestamp=time.time(),
                target_user_id=user.user_id,
                payload={"signal_id": signal_id, "lifecycle_state": ls_upper, "reason": reason_str},
                source="project1_gateway",
                correlation_id=corr_id,
                status=ls_upper,
            )
            self._notif_svc.create_notification_from_event(evt)

        return {
            "success": True,
            "signal_id": signal_id,
            "lifecycle_state": ls_upper,
            "message": f"Signal {signal_id} lifecycle state updated to {ls_upper}.",
            "correlation_id": corr_id,
        }

    def get_gateway_monitoring_summary(
        self,
        user: Optional[UserAuthorization] = None,
    ) -> Dict[str, Any]:
        """Produce gateway monitoring summary for HostSnapshot and UI presentation."""
        caps_res = self.get_capabilities(user=user)
        caps = caps_res.get("capabilities")
        recs_res = self.list_records(user=user, limit=10) if user else {"records": []}
        recs = recs_res.get("records", [])

        last_comm = recs[0].get("created_at") if recs else None
        last_comm_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(last_comm)) if last_comm else None

        return {
            "connected": True,
            "contractVersion": caps.get("current_contract_version", "1.0") if caps else "1.0",
            "supportedVersions": caps.get("supported_contract_versions", ["1.0", "1.0.0", "v1.0"]) if caps else ["1.0"],
            "ingestedRecordsCount": len(recs),
            "lastCommunicatedAt": last_comm_str,
            "capabilities": caps,
            "recentRecords": recs,
        }

    def list_records(
        self,
        user: Optional[UserAuthorization],
        symbol: Optional[str] = None,
        lifecycle_state: Optional[str] = None,
        limit: int = 100,
        timeframe: Optional[str] = None,
        from_timestamp: Optional[float] = None,
        to_timestamp: Optional[float] = None,
        signal_type: Optional[str] = None,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List integration records for the authorized user with exact filters and keyset pagination."""
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

        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 500:
            return {"success": False, "error_code": "INVALID_LIMIT", "records": [], "message": "limit must be between 1 and 500."}
        if timeframe is not None:
            from src.platform.domain.project1_contract import ALLOWED_MTF_TIMEFRAMES
            canonical = {value.lower(): value.lower() for value in ALLOWED_MTF_TIMEFRAMES}
            aliases = {"1h": "1h", "4h": "4h", "1d": "1d"}
            timeframe = (canonical | aliases).get(timeframe.strip().lower())
            if timeframe is None:
                return {"success": False, "error_code": "INVALID_TIMEFRAME", "records": [], "message": "Unsupported timeframe filter."}
        for bound_name, bound in (("from_timestamp", from_timestamp), ("to_timestamp", to_timestamp)):
            if bound is not None and (isinstance(bound, bool) or not isinstance(bound, (int, float)) or not math.isfinite(float(bound))):
                return {"success": False, "error_code": "INVALID_DATE_RANGE", "records": [], "message": f"{bound_name} must be a finite Unix timestamp."}
        if from_timestamp is not None and to_timestamp is not None and from_timestamp > to_timestamp:
            return {"success": False, "error_code": "INVALID_DATE_RANGE", "records": [], "message": "from_timestamp must not exceed to_timestamp."}

        before_timestamp = None
        before_id = None
        if cursor:
            try:
                cursor_payload = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode("utf-8"))
                before_timestamp = float(cursor_payload["timestamp"])
                before_id = str(cursor_payload["integration_id"])
                if not math.isfinite(before_timestamp) or not before_id:
                    raise ValueError("invalid cursor fields")
            except Exception:
                return {"success": False, "error_code": "INVALID_CURSOR", "records": [], "message": "cursor is malformed."}

        effective_user_id = None if user.is_admin else user.user_id
        records = self._repo.list_records_for_user(
            user_id=effective_user_id,
            symbol=symbol,
            lifecycle_state=lifecycle_state,
            limit=limit + 1,
            allow_system=True,
            timeframe=timeframe,
            from_timestamp=float(from_timestamp) if from_timestamp is not None else None,
            to_timestamp=float(to_timestamp) if to_timestamp is not None else None,
            signal_type=signal_type,
            before_timestamp=before_timestamp,
            before_integration_id=before_id,
        )
        has_more = len(records) > limit
        page = records[:limit]
        next_cursor = None
        if has_more and page:
            last = page[-1]
            next_cursor = base64.urlsafe_b64encode(json.dumps({"timestamp": float(last["timestamp"]), "integration_id": str(last["integration_id"])}, separators=(",", ":")).encode("utf-8")).decode("ascii").rstrip("=")
        sanitized_records = [SecretSanitizer.sanitize_data(r) for r in page]

        return {
            "success": True,
            "records": sanitized_records,
            "count": len(sanitized_records),
            "next_cursor": next_cursor,
        }

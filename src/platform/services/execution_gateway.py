"""Execution gateway application service.

Coordinates execution requests at the Project 2 Execution Gateway boundary.
Enforces user authentication, security boundary authorization, user/tenant isolation,
order intent lifecycle validity (STAGED only), secret sanitization, and audit logging.
Passes valid execution commands to configured ExecutionGatewayPort without altering order parameters,
claiming fills, or pretending to perform broker execution.
"""

import time
from typing import Any, Dict, Optional, Tuple

from src.platform.adapters.execution_gateway import UnavailableExecutionAdapter
from src.platform.domain.audit_control import (
    AuditCategory,
    AuditEventSeverity,
    OperationalLifecycleState,
)
from src.platform.domain.execution_gateway import (
    ExecutionAttemptResult,
    ExecutionBoundaryStatus,
    ExecutionRequestCommand,
)
from src.platform.domain.order_intent import OrderIntent, OrderLifecycleState
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.integrations.execution_gateway import ExecutionGatewayPort
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.order_intent import OrderIntentService
from src.platform.services.security import SecretSanitizer, SecurityBoundaryService


class ExecutionGatewayService:
    """Application service for the Execution Gateway Boundary."""

    def __init__(

        self,
        order_intent_service: Optional[OrderIntentService] = None,
        execution_port: Optional[ExecutionGatewayPort] = None,
        security_boundary: Optional[SecurityBoundaryService] = None,
        audit_control: Optional[PlatformAuditControlService] = None,
    ) -> None:
        self.security_boundary = security_boundary or SecurityBoundaryService()
        self.audit_control = audit_control or PlatformAuditControlService(
            security_boundary=self.security_boundary
        )
        self.order_intent_service = order_intent_service or OrderIntentService(
            security_boundary=self.security_boundary,
            audit_control=self.audit_control,
        )
        self.execution_port = execution_port or UnavailableExecutionAdapter()

    def request_execution(
        self,
        user: Optional[UserAuthorization],
        order_intent_id: str,
        execution_command_id: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> ExecutionAttemptResult:
        """Process an execution request for a staged OrderIntent through security, isolation, and gateway port."""
        ts = float(timestamp if timestamp is not None else time.time())

        # 1. Authenticated user check
        if user is None:
            self.audit_control.record_event(
                user_id="anonymous",
                category=AuditCategory.ORDER_INTENT,
                event_type="EXECUTION_REQUEST_DENIED",
                lifecycle_state=OperationalLifecycleState.REJECTED,
                action="REQUEST_EXECUTION",
                outcome="FAILURE",
                severity=AuditEventSeverity.WARNING,
                details="Execution request denied: Unauthenticated user",
            )
            return ExecutionAttemptResult(
                success=False,
                user_id="anonymous",
                order_intent_id=order_intent_id or "unknown",
                status=ExecutionBoundaryStatus.REJECTED_UNAUTHORIZED,
                reason="Unauthorized: Unauthenticated user context",
                externally_executed=False,
                detail="Authentication required to request execution.",
                timestamp=ts,
            )

        # 2. Security boundary permission check
        authorized, sec_msg = self.security_boundary.authorize(
            user=user,
            resource="signals",
            action="update",
        )
        if not authorized:
            self.audit_control.record_event(
                user_id=user.user_id,
                category=AuditCategory.ORDER_INTENT,
                event_type="EXECUTION_REQUEST_DENIED",
                lifecycle_state=OperationalLifecycleState.REJECTED,
                action="REQUEST_EXECUTION",
                outcome="FAILURE",
                severity=AuditEventSeverity.WARNING,
                details=f"Execution request denied by SecurityBoundary: {sec_msg}",
            )
            return ExecutionAttemptResult(
                success=False,
                user_id=user.user_id,
                order_intent_id=order_intent_id or "unknown",
                status=ExecutionBoundaryStatus.REJECTED_UNAUTHORIZED,
                reason=f"Unauthorized: {sec_msg}",
                externally_executed=False,
                detail="Security policy denied execution request.",
                timestamp=ts,
            )

        # 3. Retrieve OrderIntent with tenant isolation check
        success, msg, intent = self.order_intent_service.get_order_intent(
            user=user,
            order_intent_id=order_intent_id,
        )

        if not success or intent is None:
            self.audit_control.record_event(
                user_id=user.user_id,
                category=AuditCategory.ORDER_INTENT,
                event_type="EXECUTION_REQUEST_ORDER_NOT_FOUND",
                lifecycle_state=OperationalLifecycleState.REJECTED,
                action="REQUEST_EXECUTION",
                outcome="FAILURE",
                severity=AuditEventSeverity.WARNING,
                details=f"Execution request failed: {msg}",
            )
            return ExecutionAttemptResult(
                success=False,
                user_id=user.user_id,
                order_intent_id=order_intent_id,
                status=ExecutionBoundaryStatus.REJECTED_INVALID_STATE,
                reason=f"Order intent not accessible: {msg}",
                externally_executed=False,
                detail="Order intent was not found or access was restricted.",
                timestamp=ts,
            )

        # 4. OrderIntent lifecycle check (must be STAGED)
        if not intent.is_staged:
            reason_str = f"Order intent '{order_intent_id}' is in non-staged lifecycle state '{intent.lifecycle_state.value}'"
            self.audit_control.record_event(
                user_id=user.user_id,
                category=AuditCategory.ORDER_INTENT,
                event_type="EXECUTION_REQUEST_INVALID_STATE",
                lifecycle_state=intent.lifecycle_state,
                action="REQUEST_EXECUTION",
                outcome="FAILURE",
                severity=AuditEventSeverity.WARNING,
                resource_id=order_intent_id,
                details=reason_str,
            )
            return ExecutionAttemptResult(
                success=False,
                user_id=user.user_id,
                order_intent_id=order_intent_id,
                status=ExecutionBoundaryStatus.REJECTED_INVALID_STATE,
                reason=reason_str,
                externally_executed=False,
                detail="Only OrderIntents in STAGED state can be submitted to the execution boundary.",
                timestamp=ts,
            )

        # 5. Build ExecutionRequestCommand derived strictly from OrderIntent
        try:
            cmd = ExecutionRequestCommand.from_order_intent(
                order_intent=intent,
                command_id=execution_command_id,
                timestamp=ts,
            )
        except ValueError as exc:
            err_msg = f"Failed to construct ExecutionRequestCommand: {exc}"
            self.audit_control.record_event(
                user_id=user.user_id,
                category=AuditCategory.ORDER_INTENT,
                event_type="EXECUTION_COMMAND_CREATION_FAILED",
                lifecycle_state=OperationalLifecycleState.FAILED,
                action="REQUEST_EXECUTION",
                outcome="FAILURE",
                severity=AuditEventSeverity.ERROR,
                resource_id=order_intent_id,
                details=err_msg,
            )
            return ExecutionAttemptResult(
                success=False,
                user_id=user.user_id,
                order_intent_id=order_intent_id,
                status=ExecutionBoundaryStatus.REJECTED_INVALID_STATE,
                reason=err_msg,
                externally_executed=False,
                detail="Command construction failed.",
                timestamp=ts,
            )

        # 6. Submit command to ExecutionGatewayPort
        result = self.execution_port.request_execution(cmd)

        # 7. Audit log execution attempt
        audit_severity = AuditEventSeverity.INFO if result.success else AuditEventSeverity.WARNING
        self.audit_control.record_event(
            user_id=user.user_id,
            category=AuditCategory.ORDER_INTENT,
            event_type=f"EXECUTION_BOUNDARY_{result.status.value}",
            lifecycle_state=OperationalLifecycleState.REJECTED if not result.success else OperationalLifecycleState.STAGED,
            action="REQUEST_EXECUTION",
            outcome="SUCCESS" if result.success else "REJECTED",
            severity=audit_severity,
            resource_id=order_intent_id,
            correlation_id=cmd.idempotency_key,
            details=f"Execution boundary request status: {result.status.value}. Reason: {result.reason}",
            metadata={
                "externally_executed": result.externally_executed,
                "provider_id": result.provider_id,
                "symbol": cmd.symbol,
                "direction": cmd.direction,
                "order_type": cmd.order_type,
            },
        )

        return result

    def get_boundary_status(
        self, user: Optional[UserAuthorization] = None
    ) -> Dict[str, Any]:
        """Return I/O-free description and capability status of the execution gateway boundary."""
        port_desc = self.execution_port.describe()
        sanitized_desc = SecretSanitizer.sanitize_data(port_desc)

        return {
            "boundary_name": "Project 2 Execution Gateway Boundary",
            "status": "configured" if sanitized_desc.get("configured") else "unconfigured",
            "allows_execution": bool(sanitized_desc.get("allows_execution", False)),
            "provider": sanitized_desc,
            "notice": "OrderIntents represent staged execution intent. Project 2 does not execute orders against live brokers or exchanges.",
        }

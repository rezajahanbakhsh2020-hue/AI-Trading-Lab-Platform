"""Order intent application service (Part 16: Order Intent & Lifecycle Foundation).

Creates, transitions, and retrieves authorized order intents from existing
AutonomousAuthorization outcomes without performing price recalculations or claiming
broker execution, fills, or routing.
"""

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

from src.platform.domain.audit_control import (
    AuditCategory,
    AuditEventSeverity,
    OperationalLifecycleState,
)
from src.platform.domain.autonomous_authorization import AutonomousAuthorization
from src.platform.domain.order_intent import (
    OrderIntent,
    OrderLifecycleState,
    validate_lifecycle_transition,
)
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.security import SecurityBoundaryService


class OrderIntentService:
    """Application service for managing authorized order intents."""

    def __init__(
        self,
        security_boundary: Optional[SecurityBoundaryService] = None,
        audit_control: Optional[PlatformAuditControlService] = None,
    ) -> None:
        self.security_boundary = security_boundary or SecurityBoundaryService()
        self.audit_control = audit_control or PlatformAuditControlService(
            security_boundary=self.security_boundary
        )
        # Store in-memory indexed by order_intent_id
        self._intents_by_id: Dict[str, OrderIntent] = {}
        # Store idempotency map: (user_id, idempotency_key) -> order_intent_id
        self._idempotency_map: Dict[Tuple[str, str], str] = {}

    def create_order_intent(
        self,
        user: Optional[UserAuthorization],
        authorization: AutonomousAuthorization,
        idempotency_key: str,
        symbol: Optional[str] = None,
        order_type: str = "market",
        requested_quantity: Optional[float] = None,
        time_in_force: Optional[str] = None,
        timestamp: Optional[Union[int, float]] = None,
    ) -> Tuple[bool, str, Optional[OrderIntent]]:
        """Create a staged OrderIntent from an authorized AutonomousAuthorization result."""
        # 1. User authorization check
        if user is None:
            self.audit_control.record_event(
                user_id="anonymous",
                category=AuditCategory.ORDER_INTENT,
                event_type="ORDER_INTENT_CREATION_DENIED",
                lifecycle_state=OperationalLifecycleState.REJECTED,
                action="CREATE_ORDER_INTENT",
                outcome="FAILURE",
                severity=AuditEventSeverity.WARNING,
                details="Unauthorized order intent creation attempt: No user provided",
            )
            return False, "Unauthorized: Access denied: unauthenticated access", None

        authorized, sec_msg = self.security_boundary.authorize(
            user=user,
            resource="signals",
            action="create",
        )
        if not authorized:
            self.audit_control.record_event(
                user_id=user.user_id,
                category=AuditCategory.ORDER_INTENT,
                event_type="ORDER_INTENT_CREATION_DENIED",
                lifecycle_state=OperationalLifecycleState.REJECTED,
                action="CREATE_ORDER_INTENT",
                outcome="FAILURE",
                severity=AuditEventSeverity.WARNING,
                details=f"Unauthorized order intent creation attempt: {sec_msg}",
            )
            return False, f"Unauthorized: {sec_msg}", None

        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            return False, "idempotency_key must be a non-empty string", None

        clean_idempotency_key = idempotency_key.strip()
        user_id = user.user_id

        # 2. Idempotency check: if already created for (user_id, idempotency_key), return existing
        idempotency_pair = (user_id, clean_idempotency_key)
        if idempotency_pair in self._idempotency_map:
            existing_id = self._idempotency_map[idempotency_pair]
            existing_intent = self._intents_by_id.get(existing_id)
            if existing_intent is not None:
                self.audit_control.record_event(
                    user_id=user_id,
                    category=AuditCategory.ORDER_INTENT,
                    event_type="ORDER_INTENT_IDEMPOTENT_DUPLICATE",
                    lifecycle_state=existing_intent.lifecycle_state,
                    action="CREATE_ORDER_INTENT",
                    outcome="SUCCESS",
                    severity=AuditEventSeverity.INFO,
                    resource_id=existing_intent.order_intent_id,
                    correlation_id=clean_idempotency_key,
                    details="Returned existing order intent for idempotent key without duplication.",
                )
                return True, "Existing order intent returned (idempotent)", existing_intent

        # 3. Validate AutonomousAuthorization
        if not isinstance(authorization, AutonomousAuthorization):
            return False, "authorization must be an AutonomousAuthorization instance", None

        if not authorization.is_authorized:
            reason = f"AutonomousAuthorization is not authorized: {authorization.reason}"
            self.audit_control.record_event(
                user_id=user_id,
                category=AuditCategory.ORDER_INTENT,
                event_type="ORDER_INTENT_AUTHORIZATION_REJECTED",
                lifecycle_state=OperationalLifecycleState.REJECTED,
                action="CREATE_ORDER_INTENT",
                outcome="REJECTED",
                severity=AuditEventSeverity.WARNING,
                correlation_id=clean_idempotency_key,
                details=reason,
            )
            return False, reason, None

        # 4. Extract upstream trade parameters WITHOUT recalculation or invention
        trade_signal = authorization.trade_signal
        trade_setup = trade_signal.trade_setup

        target_symbol = symbol.strip().upper() if symbol and symbol.strip() else None
        if target_symbol is None and trade_setup is not None:
            target_symbol = trade_setup.symbol

        if not target_symbol:
            reason = "Missing required symbol from upstream trade setup or input"
            self.audit_control.record_event(
                user_id=user_id,
                category=AuditCategory.ORDER_INTENT,
                event_type="ORDER_INTENT_MISSING_DATA",
                lifecycle_state=OperationalLifecycleState.FAILED,
                action="CREATE_ORDER_INTENT",
                outcome="FAILURE",
                severity=AuditEventSeverity.ERROR,
                correlation_id=clean_idempotency_key,
                details=reason,
            )
            return False, reason, None

        direction = trade_setup.direction if trade_setup is not None else trade_signal.signal.action
        if direction not in ("buy", "sell"):
            reason = f"Invalid trading direction '{direction}' for order intent creation"
            return False, reason, None

        entry_price = trade_setup.entry_price if trade_setup is not None else None
        stop_loss = trade_setup.stop_loss if trade_setup is not None else None
        tp1 = trade_setup.take_profit_1 if trade_setup is not None else None
        tp2 = trade_setup.take_profit_2 if trade_setup is not None else None
        tp3 = trade_setup.take_profit_3 if trade_setup is not None else None

        auth_id = f"auth_{int(authorization.timestamp)}_{trade_signal.signal.strategy_name}"
        order_intent_id = f"ord_intent_{uuid.uuid4().hex[:12]}"
        creation_ts = float(timestamp if timestamp is not None else time.time())

        try:
            intent = OrderIntent(
                order_intent_id=order_intent_id,
                authorization_id=auth_id,
                user_id=user_id,
                symbol=target_symbol,
                direction=direction,
                idempotency_key=clean_idempotency_key,
                creation_timestamp=creation_ts,
                lifecycle_state=OrderLifecycleState.STAGED,
                order_type=order_type,
                requested_price=entry_price,
                requested_quantity=requested_quantity,
                stop_loss=stop_loss,
                take_profit_1=tp1,
                take_profit_2=tp2,
                take_profit_3=tp3,
                time_in_force=time_in_force,
            )
        except ValueError as e:
            reason = f"Failed to construct OrderIntent: {e}"
            return False, reason, None

        # 5. Store order intent
        self._intents_by_id[intent.order_intent_id] = intent
        self._idempotency_map[idempotency_pair] = intent.order_intent_id

        # 6. Audit logging
        self.audit_control.record_event(
            user_id=user_id,
            category=AuditCategory.ORDER_INTENT,
            event_type="ORDER_INTENT_STAGED",
            lifecycle_state=OperationalLifecycleState.STAGED,
            action="CREATE_ORDER_INTENT",
            outcome="SUCCESS",
            severity=AuditEventSeverity.INFO,
            resource_id=intent.order_intent_id,
            correlation_id=clean_idempotency_key,
            details=f"Order intent staged for symbol {target_symbol} ({direction.upper()}) without external execution.",
            metadata={
                "order_intent_id": intent.order_intent_id,
                "symbol": target_symbol,
                "direction": direction,
                "order_type": intent.order_type,
                "has_entry_price": entry_price is not None,
                "has_stop_loss": stop_loss is not None,
                "has_take_profits": tp1 is not None,
            },
        )

        return True, "Order intent staged successfully", intent

    def transition_order_intent_state(
        self,
        user: Optional[UserAuthorization],
        order_intent_id: str,
        target_state: Union[OrderLifecycleState, str],
        reason: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[OrderIntent]]:
        """Transition the lifecycle state of an existing order intent."""
        if user is None:
            return False, "Unauthorized: Access denied: unauthenticated access", None

        authorized, sec_msg = self.security_boundary.authorize(
            user=user,
            resource="signals",
            action="update",
        )
        if not authorized:
            return False, f"Unauthorized: {sec_msg}", None

        if not isinstance(order_intent_id, str) or not order_intent_id.strip():
            return False, "order_intent_id must be a non-empty string", None

        clean_id = order_intent_id.strip()
        intent = self._intents_by_id.get(clean_id)

        if intent is None:
            return False, f"Order intent '{clean_id}' not found", None

        # Multi-tenant user isolation check
        if not user.is_admin and intent.user_id != user.user_id:
            reason_msg = f"User '{user.user_id}' cannot modify order intent belonging to '{intent.user_id}'"
            self.audit_control.record_event(
                user_id=user.user_id,
                category=AuditCategory.ORDER_INTENT,
                event_type="ORDER_INTENT_ACCESS_DENIED",
                lifecycle_state=OperationalLifecycleState.REJECTED,
                action="TRANSITION_ORDER_INTENT_STATE",
                outcome="FAILURE",
                severity=AuditEventSeverity.WARNING,
                resource_id=clean_id,
                details=reason_msg,
            )
            return False, f"Unauthorized: {reason_msg}", None

        try:
            if isinstance(target_state, str):
                target_state = OrderLifecycleState(target_state.upper())
            updated_intent = intent.with_lifecycle_state(target_state, reason=reason)
        except ValueError as e:
            err_msg = str(e)
            self.audit_control.record_event(
                user_id=user.user_id,
                category=AuditCategory.ORDER_INTENT,
                event_type="ORDER_INTENT_INVALID_TRANSITION",
                lifecycle_state=intent.lifecycle_state,
                action="TRANSITION_ORDER_INTENT_STATE",
                outcome="FAILURE",
                severity=AuditEventSeverity.WARNING,
                resource_id=clean_id,
                details=f"Invalid lifecycle state transition attempt: {err_msg}",
            )
            return False, err_msg, intent

        # Save updated intent
        self._intents_by_id[clean_id] = updated_intent

        audit_lifecycle = (
            OperationalLifecycleState.CANCELLED
            if target_state == OrderLifecycleState.CANCELLED
            else (
                OperationalLifecycleState.EXPIRED
                if target_state == OrderLifecycleState.EXPIRED
                else OperationalLifecycleState.REJECTED
            )
        )

        self.audit_control.record_event(
            user_id=user.user_id,
            category=AuditCategory.ORDER_INTENT,
            event_type=f"ORDER_INTENT_{target_state.value}",
            lifecycle_state=audit_lifecycle,
            action="TRANSITION_ORDER_INTENT_STATE",
            outcome="SUCCESS",
            severity=AuditEventSeverity.INFO,
            resource_id=clean_id,
            details=f"Order intent state transitioned to {target_state.value}. {reason or ''}".strip(),
        )

        return True, f"Order intent state transitioned to {target_state.value}", updated_intent

    def get_order_intent(
        self, user: Optional[UserAuthorization], order_intent_id: str
    ) -> Tuple[bool, str, Optional[OrderIntent]]:
        """Retrieve an order intent by ID with user isolation enforcement."""
        if user is None:
            return False, "Unauthorized: Access denied: unauthenticated access", None

        authorized, sec_msg = self.security_boundary.authorize(
            user=user,
            resource="signals",
            action="read",
        )
        if not authorized:
            return False, f"Unauthorized: {sec_msg}", None

        if not isinstance(order_intent_id, str) or not order_intent_id.strip():
            return False, "order_intent_id must be a non-empty string", None

        clean_id = order_intent_id.strip()
        intent = self._intents_by_id.get(clean_id)

        if intent is None:
            return False, f"Order intent '{clean_id}' not found", None

        # User isolation check
        if not user.is_admin and intent.user_id != user.user_id:
            return False, "Unauthorized: Cannot access order intent belonging to another user", None

        return True, "Order intent retrieved successfully", intent

    def list_order_intents(
        self,
        user: Optional[UserAuthorization],
        symbol: Optional[str] = None,
        lifecycle_state: Optional[Union[OrderLifecycleState, str]] = None,
    ) -> Tuple[bool, str, List[OrderIntent]]:
        """List order intents for an authorized user with tenant isolation."""
        if user is None:
            return False, "Unauthorized: Access denied: unauthenticated access", []

        authorized, sec_msg = self.security_boundary.authorize(
            user=user,
            resource="signals",
            action="read",
        )
        if not authorized:
            return False, f"Unauthorized: {sec_msg}", []

        results: List[OrderIntent] = []
        target_symbol = symbol.strip().upper() if symbol and symbol.strip() else None

        target_state = None
        if lifecycle_state:
            if isinstance(lifecycle_state, str):
                try:
                    target_state = OrderLifecycleState(lifecycle_state.upper())
                except ValueError:
                    return False, f"Invalid lifecycle state filter: {lifecycle_state}", []
            elif isinstance(lifecycle_state, OrderLifecycleState):
                target_state = lifecycle_state

        for intent in self._intents_by_id.values():
            # User isolation filter
            if not user.is_admin and intent.user_id != user.user_id:
                continue

            if target_symbol and intent.symbol != target_symbol:
                continue

            if target_state and intent.lifecycle_state != target_state:
                continue

            results.append(intent)

        results.sort(key=lambda x: x.creation_timestamp, reverse=True)
        return True, "Order intents retrieved successfully", results

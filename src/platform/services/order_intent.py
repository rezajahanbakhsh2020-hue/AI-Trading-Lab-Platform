"""Order intent application service (Part 16: Order Intent & Lifecycle Foundation).

Creates, transitions, and retrieves authorized order intents from existing
AutonomousAuthorization outcomes without performing price recalculations or claiming
broker execution, fills, or routing.
"""

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

from src.platform.adapters.order_intent_repository import OrderIntentRepositoryPort
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
        repository: Optional[OrderIntentRepositoryPort] = None,
        notification_service: Optional[Any] = None,
        project1_gateway_service: Optional[Any] = None,
    ) -> None:
        self.security_boundary = security_boundary or SecurityBoundaryService()
        self.audit_control = audit_control or PlatformAuditControlService(
            security_boundary=self.security_boundary
        )
        self.repository = repository
        self.notification_service = notification_service
        self.project1_gateway_service = project1_gateway_service
        # Store in-memory indexed by order_intent_id
        self._intents_by_id: Dict[str, OrderIntent] = {}
        # Store idempotency map: (user_id, idempotency_key) -> order_intent_id
        self._idempotency_map: Dict[Tuple[str, str], str] = {}

    def _extract_canonical_content_tuple(self, source: Any) -> Tuple[Any, ...]:
        """Extract a deterministic tuple of all 19 authoritative trade & lineage fields for integrity comparisons."""
        if isinstance(source, OrderIntent):
            d = source.to_dict()
        elif isinstance(source, dict):
            d = source
        else:
            return ()

        trailing = d.get("trailing_stop")
        trailing_tuple = tuple(sorted(trailing.items())) if isinstance(trailing, dict) else None

        return (
            d.get("publication_id"),
            d.get("signal_id"),
            d.get("decision_id"),
            d.get("canonical_live_decision_fingerprint"),
            d.get("candidate_id"),
            d.get("research_evidence_id"),
            d.get("strategy_id") or d.get("strategy_name"),
            d.get("research_fingerprint"),
            d.get("runtime_authorization_fingerprint"),
            d.get("strategy_version"),
            d.get("symbol"),
            d.get("direction") or d.get("signal_type"),
            d.get("requested_price") if "requested_price" in d else d.get("entry_price"),
            d.get("stop_loss"),
            d.get("take_profit_1"),
            d.get("take_profit_2"),
            d.get("take_profit_3"),
            d.get("requested_quantity") if "requested_quantity" in d else d.get("quantity"),
            trailing_tuple,
            d.get("invalidation_condition"),
        )

    def create_canonical_order_intent_from_publication(
        self,
        user: Optional[UserAuthorization],
        publication_id: str,
        idempotency_key: Optional[str] = None,
        project1_gateway_service: Optional[Any] = None,
    ) -> Tuple[bool, str, Optional[OrderIntent]]:
        """Authoritative server-side creation of canonical OrderIntent from Project 1 publication record."""
        if user is None:
            self.audit_control.record_event(
                user_id="anonymous",
                category=AuditCategory.ORDER_INTENT,
                event_type="ORDER_INTENT_CREATION_DENIED",
                lifecycle_state=OperationalLifecycleState.REJECTED,
                action="CREATE_CANONICAL_ORDER_INTENT",
                outcome="FAILURE",
                severity=AuditEventSeverity.WARNING,
                details="Unauthorized canonical order intent creation attempt: No user provided",
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
                action="CREATE_CANONICAL_ORDER_INTENT",
                outcome="FAILURE",
                severity=AuditEventSeverity.WARNING,
                details=f"Unauthorized canonical order intent creation attempt: {sec_msg}",
            )
            return False, f"Unauthorized: {sec_msg}", None

        if not isinstance(publication_id, str) or not publication_id.strip():
            return False, "publication_id must be a non-empty string", None

        clean_pub_id = publication_id.strip()
        user_id = user.user_id

        # 2. Resolve authoritative Project 1 integration record server-side via public Gateway API
        gw_svc = project1_gateway_service or self.project1_gateway_service
        p1_record: Optional[Dict[str, Any]] = None

        if gw_svc is not None and hasattr(gw_svc, "resolve_authoritative_publication"):
            p1_record = gw_svc.resolve_authoritative_publication(user, clean_pub_id)

        if p1_record is None:
            reason = f"No authoritative Project 1 integration record found for publication_id '{clean_pub_id}'"
            self.audit_control.record_event(
                user_id=user_id,
                category=AuditCategory.ORDER_INTENT,
                event_type="ORDER_INTENT_RECORD_NOT_FOUND",
                lifecycle_state=OperationalLifecycleState.FAILED,
                action="CREATE_CANONICAL_ORDER_INTENT",
                outcome="FAILURE",
                severity=AuditEventSeverity.WARNING,
                correlation_id=clean_pub_id,
                details=reason,
            )
            return False, reason, None

        # 3. Verify complete mandatory lineage identity (Fail closed if missing)
        pub_id = p1_record.get("publication_id")
        sig_id = p1_record.get("signal_id")
        dec_id = p1_record.get("decision_id")
        canon_fp = p1_record.get("canonical_live_decision_fingerprint")
        cand_id = p1_record.get("candidate_id")
        rese_id = p1_record.get("research_evidence_id")
        strat_id = p1_record.get("strategy_name") or p1_record.get("strategy_id")
        rese_fp = p1_record.get("research_fingerprint")
        runtime_auth_fp = p1_record.get("runtime_authorization_fingerprint")
        strat_ver = p1_record.get("strategy_version")

        lineage_checks = {
            "publication_id": pub_id,
            "signal_id": sig_id,
            "decision_id": dec_id,
            "canonical_live_decision_fingerprint": canon_fp,
            "candidate_id": cand_id,
            "research_evidence_id": rese_id,
            "strategy_id": strat_id,
            "research_fingerprint": rese_fp,
            "runtime_authorization_fingerprint": runtime_auth_fp,
        }

        for field_key, val in lineage_checks.items():
            if not val or not isinstance(val, str) or not val.strip():
                reason = f"Missing mandatory authoritative lineage field '{field_key}' in Project 1 record"
                self.audit_control.record_event(
                    user_id=user_id,
                    category=AuditCategory.ORDER_INTENT,
                    event_type="ORDER_INTENT_LINEAGE_MISSING",
                    lifecycle_state=OperationalLifecycleState.FAILED,
                    action="CREATE_CANONICAL_ORDER_INTENT",
                    outcome="FAILURE",
                    severity=AuditEventSeverity.ERROR,
                    correlation_id=clean_pub_id,
                    details=reason,
                )
                return False, reason, None

        # 4. Extract trade values strictly from P1 record without calculation, modification, or invention
        symbol = p1_record.get("symbol")
        if not symbol or not isinstance(symbol, str) or not symbol.strip():
            return False, "Missing or invalid symbol in Project 1 record", None
        clean_symbol = symbol.strip().upper()

        raw_direction = p1_record.get("signal_type") or p1_record.get("direction")
        if not raw_direction or not isinstance(raw_direction, str):
            return False, "Missing or invalid signal_type/direction in Project 1 record", None
        clean_dir = raw_direction.strip().lower()
        if clean_dir not in ("buy", "sell"):
            return False, f"Non-actionable or unsupported signal decision '{raw_direction}' in Project 1 record", None

        entry_price = p1_record.get("entry_price")
        stop_loss = p1_record.get("stop_loss")
        tp1 = p1_record.get("take_profit_1")
        tp2 = p1_record.get("take_profit_2")
        tp3 = p1_record.get("take_profit_3")
        trailing_stop = p1_record.get("trailing_stop")
        invalidation = p1_record.get("invalidation_condition")
        if invalidation is None and isinstance(p1_record.get("metadata"), dict):
            invalidation = p1_record["metadata"].get("invalidation_condition")

        # Quantity must NOT be invented or caller-supplied. Only preserve if present in authoritative P1 record.
        p1_quantity = p1_record.get("requested_quantity") or p1_record.get("quantity")
        requested_quantity = float(p1_quantity) if p1_quantity is not None else None

        clean_idemp_key = (
            idempotency_key.strip()
            if idempotency_key and isinstance(idempotency_key, str) and idempotency_key.strip()
            else f"idemp_pub_{user_id}_{pub_id}"
        )

        # Build candidate dict for content comparison
        calculated_p1_dict = {
            "publication_id": pub_id,
            "signal_id": sig_id,
            "decision_id": dec_id,
            "canonical_live_decision_fingerprint": canon_fp,
            "candidate_id": cand_id,
            "research_evidence_id": rese_id,
            "strategy_id": strat_id,
            "research_fingerprint": rese_fp,
            "runtime_authorization_fingerprint": runtime_auth_fp,
            "strategy_version": strat_ver,
            "symbol": clean_symbol,
            "direction": clean_dir,
            "requested_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "take_profit_3": tp3,
            "requested_quantity": requested_quantity,
            "trailing_stop": trailing_stop,
            "invalidation_condition": invalidation,
        }

        # 5. Idempotency & Integrity Conflict Checks (strictly publication_id based)
        existing_intent: Optional[OrderIntent] = None
        all_intents = self._intents_by_id.values()
        if self.repository is not None:
            all_intents = self.repository.list_order_intents(user_id=None if user.is_admin else user_id)

        for candidate_intent in all_intents:
            if not user.is_admin and candidate_intent.user_id != user_id:
                continue
            if candidate_intent.publication_id == pub_id:
                existing_intent = candidate_intent
                break

        if existing_intent is not None:
            existing_content = self._extract_canonical_content_tuple(existing_intent)
            p1_content = self._extract_canonical_content_tuple(calculated_p1_dict)

            if existing_content == p1_content:
                self.audit_control.record_event(
                    user_id=user_id,
                    category=AuditCategory.ORDER_INTENT,
                    event_type="ORDER_INTENT_IDEMPOTENT_DUPLICATE",
                    lifecycle_state=existing_intent.lifecycle_state,
                    action="CREATE_CANONICAL_ORDER_INTENT",
                    outcome="SUCCESS",
                    severity=AuditEventSeverity.INFO,
                    resource_id=existing_intent.order_intent_id,
                    correlation_id=clean_idemp_key,
                    details="Returned existing canonical order intent for idempotent publication without duplication.",
                )
                return True, "Existing canonical order intent returned (idempotent)", existing_intent
            else:
                reason = "Integrity conflict: Existing order intent for publication identity contains mutated authoritative content"
                self.audit_control.record_event(
                    user_id=user_id,
                    category=AuditCategory.ORDER_INTENT,
                    event_type="ORDER_INTENT_INTEGRITY_CONFLICT",
                    lifecycle_state=OperationalLifecycleState.REJECTED,
                    action="CREATE_CANONICAL_ORDER_INTENT",
                    outcome="FAILURE",
                    severity=AuditEventSeverity.ERROR,
                    correlation_id=clean_idemp_key,
                    details=reason,
                )
                return False, reason, None

        # Also verify that caller-supplied idempotency key does not belong to a different publication intent
        idempotency_pair = (user_id, clean_idemp_key)
        if idempotency_pair in self._idempotency_map:
            key_intent_id = self._idempotency_map[idempotency_pair]
            key_intent = self._intents_by_id.get(key_intent_id)
            if key_intent and key_intent.publication_id != pub_id:
                reason = f"Idempotency key '{clean_idemp_key}' is already bound to a different publication intent"
                return False, reason, None

        # 6. Construct and persist canonical OrderIntent (authorization_id is None)
        order_intent_id = f"ord_intent_{uuid.uuid4().hex[:12]}"
        creation_ts = float(p1_record.get("timestamp") or time.time())

        try:
            intent = OrderIntent(
                order_intent_id=order_intent_id,
                authorization_id=None,  # Canonical P1 intents have no synthetic authorization_id
                user_id=user_id,
                symbol=clean_symbol,
                direction=clean_dir,
                idempotency_key=clean_idemp_key,
                creation_timestamp=creation_ts,
                lifecycle_state=OrderLifecycleState.STAGED,
                order_type="market",
                requested_price=entry_price,
                requested_quantity=requested_quantity,
                stop_loss=stop_loss,
                take_profit_1=tp1,
                take_profit_2=tp2,
                take_profit_3=tp3,
                publication_id=pub_id,
                signal_id=sig_id,
                decision_id=dec_id,
                canonical_live_decision_fingerprint=canon_fp,
                candidate_id=cand_id,
                research_evidence_id=rese_id,
                strategy_id=strat_id,
                research_fingerprint=rese_fp,
                runtime_authorization_fingerprint=runtime_auth_fp,
                strategy_version=strat_ver,
                trailing_stop=trailing_stop if isinstance(trailing_stop, dict) else None,
                invalidation_condition=invalidation if isinstance(invalidation, str) else None,
            )
        except ValueError as e:
            reason = f"Failed constructing canonical OrderIntent: {e}"
            return False, reason, None

        self._intents_by_id[intent.order_intent_id] = intent
        self._idempotency_map[(user_id, clean_idemp_key)] = intent.order_intent_id
        if self.repository is not None:
            self.repository.save_order_intent(intent)

        self.audit_control.record_event(
            user_id=user_id,
            category=AuditCategory.ORDER_INTENT,
            event_type="CANONICAL_ORDER_INTENT_STAGED",
            lifecycle_state=OperationalLifecycleState.STAGED,
            action="CREATE_CANONICAL_ORDER_INTENT",
            outcome="SUCCESS",
            severity=AuditEventSeverity.INFO,
            resource_id=intent.order_intent_id,
            correlation_id=clean_idemp_key,
            details=f"Canonical OrderIntent staged for publication {pub_id} ({clean_symbol} {clean_dir.upper()})",
            metadata={
                "order_intent_id": intent.order_intent_id,
                "publication_id": pub_id,
                "signal_id": sig_id,
                "strategy_id": strat_id,
                "runtime_authorization_fingerprint": runtime_auth_fp,
            },
        )

        return True, "Canonical order intent staged successfully", intent

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
        existing_intent = None
        if self.repository is not None:
            existing_intent = self.repository.get_by_idempotency_key(user_id, clean_idempotency_key)
        elif idempotency_pair in self._idempotency_map:
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
        if self.repository is not None:
            self.repository.save_order_intent(intent)

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

        # 7. Dispatch canonical notification event
        if self.notification_service is not None:
            try:
                from src.platform.domain.notification import (
                    NotificationCategory,
                    NotificationEvent,
                    NotificationSeverity,
                )
                evt = NotificationEvent(
                    event_id=f"evt_order_staged_{intent.order_intent_id}",
                    event_type="ORDER_INTENT_STAGED",
                    category=NotificationCategory.SIGNAL_LIFECYCLE,
                    severity=NotificationSeverity.INFO,
                    title=f"Order Intent Staged ({intent.symbol})",
                    message=f"Order intent staged for {intent.symbol} ({intent.direction.upper()}) at price {intent.requested_price or 'Market'}.",
                    timestamp=intent.creation_timestamp,
                    target_user_id=intent.user_id,
                    payload={
                        "order_intent_id": intent.order_intent_id,
                        "symbol": intent.symbol,
                        "direction": intent.direction,
                        "lifecycle_state": intent.lifecycle_state.value,
                    },
                )
                self.notification_service.create_notification_from_event(evt)
            except Exception:
                pass

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
        intent = None
        if self.repository is not None:
            intent = self.repository.get_order_intent(clean_id, user_id=None if user.is_admin else user.user_id)
        else:
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
        if self.repository is not None:
            self.repository.save_order_intent(updated_intent)

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

        # Dispatch canonical notification event
        if self.notification_service is not None:
            try:
                from src.platform.domain.notification import (
                    NotificationCategory,
                    NotificationEvent,
                    NotificationSeverity,
                )
                sev = (
                    NotificationSeverity.WARNING
                    if target_state in (OrderLifecycleState.CANCELLED, OrderLifecycleState.REJECTED)
                    else NotificationSeverity.INFO
                )
                evt = NotificationEvent(
                    event_id=f"evt_order_{target_state.value.lower()}_{updated_intent.order_intent_id}_{int(time.time())}",
                    event_type=f"ORDER_INTENT_{target_state.value}",
                    category=NotificationCategory.SIGNAL_LIFECYCLE,
                    severity=sev,
                    title=f"Order Intent {target_state.value.capitalize()} ({updated_intent.symbol})",
                    message=f"Order intent '{updated_intent.order_intent_id}' transitioned to {target_state.value}. {reason or ''}".strip(),
                    timestamp=time.time(),
                    target_user_id=updated_intent.user_id,
                    payload={
                        "order_intent_id": updated_intent.order_intent_id,
                        "symbol": updated_intent.symbol,
                        "lifecycle_state": updated_intent.lifecycle_state.value,
                        "reason": reason,
                    },
                )
                self.notification_service.create_notification_from_event(evt)
            except Exception:
                pass

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
        intent = None
        if self.repository is not None:
            intent = self.repository.get_order_intent(clean_id, user_id=None if user.is_admin else user.user_id)
        else:
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

        ls_str = None
        if lifecycle_state:
            ls_str = lifecycle_state.value if isinstance(lifecycle_state, OrderLifecycleState) else str(lifecycle_state)

        if self.repository is not None:
            intents = self.repository.list_order_intents(
                user_id=None if user.is_admin else user.user_id,
                symbol=symbol,
                lifecycle_state=ls_str,
            )
            return True, "Order intents retrieved successfully", intents

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

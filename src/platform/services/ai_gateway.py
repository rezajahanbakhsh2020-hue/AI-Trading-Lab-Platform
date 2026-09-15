"""Secure AI Gateway Service for platform context isolation, authorization, and AI provider delegation.

Enforces authorization BEFORE context reaches any AI provider. Guarantees that only
permitted, sanitized, user-scoped platform information enters AI context, preventing exposure
of Project 1 proprietary logic, indicators, strategy parameters, credentials, or secrets.
"""

import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from src.platform.adapters.ai_provider import (
    AIProviderPort,
    UnavailableAIProviderAdapter,
)
from src.platform.domain.ai_gateway import (
    AICapability,
    AIProviderStatus,
    AIRequest,
    AIResponse,
    AllowedIntelligenceContext,
)
from src.platform.domain.security import Permission
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.security import (
    AuditLogger,
    SecretSanitizer,
    SecurityBoundaryService,
)


class AIGatewayService:
    """Production AI boundary managing permitted context generation and AI provider interaction."""

    PROHIBITED_KEYWORDS: Set[str] = {
        "indicator_logic",
        "strategy_params",
        "sensitive_parameters",
        "lab_secrets",
        "credentials",
        "auth_code",
        "private_key",
        "api_key",
        "best_strategies",
        "lab_research",
    }

    CAPABILITY_PERMISSIONS: Dict[AICapability, Tuple[str, Permission]] = {
        AICapability.EXPLAIN_SIGNAL: ("signals", Permission.READ_SIGNALS),
        AICapability.SUMMARIZE_MARKET: ("market", Permission.READ_SIGNALS),
        AICapability.SUMMARIZE_TIMELINE: ("timeline", Permission.READ_SIGNALS),
        AICapability.EXPLAIN_HEALTH: ("health", Permission.READ_SIGNALS),
    }

    def __init__(
        self,
        security_boundary: Optional[SecurityBoundaryService] = None,
        audit_logger: Optional[AuditLogger] = None,
        provider: Optional[AIProviderPort] = None,
    ) -> None:
        self.audit_logger = audit_logger or AuditLogger()
        self.security_boundary = security_boundary or SecurityBoundaryService(
            audit_logger=self.audit_logger
        )
        self._provider = provider or UnavailableAIProviderAdapter()

    def set_provider(self, provider: AIProviderPort) -> None:
        """Set or replace the AI Provider Adapter (cloud, local model, or test mock)."""
        if not isinstance(provider, AIProviderPort):
            raise ValueError("provider must implement AIProviderPort")
        self._provider = provider

    def get_provider(self) -> AIProviderPort:
        """Return the currently attached AI Provider Adapter."""
        return self._provider

    def build_allowed_context(
        self,
        user: Optional[UserAuthorization],
        capability: AICapability,
        target_symbol: Optional[str] = None,
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[AllowedIntelligenceContext], str]:
        """Construct a minimal, permission-filtered, user-scoped, and non-secret AI context."""
        user_id = user.user_id if user else "anonymous"

        # 1. Evaluate Authorization BEFORE context construction
        resource_name, required_perm = self.CAPABILITY_PERMISSIONS.get(
            capability, ("signals", Permission.READ_SIGNALS)
        )

        authorized, auth_reason = self.security_boundary.authorize(
            user=user,
            resource=resource_name,
            action="ai_explain",
            required_permission=required_perm,
        )

        if not authorized:
            self.audit_logger.log(
                user_id=user_id,
                event_type="AI_REQUEST_DENIED",
                resource="ai_gateway",
                action="build_context",
                outcome="DENY",
                details=f"Authorization failed for capability '{capability.value}': {auth_reason}",
            )
            return False, None, auth_reason

        # 2. Sanitize and filter input snapshot data
        snap_data = snapshot if isinstance(snapshot, dict) else {}
        filtered_snapshot = self.security_boundary.filter_protected_payload(user, snap_data)
        sanitized_snapshot = SecretSanitizer.sanitize_data(filtered_snapshot)

        # 3. Explicit Prohibited Secret & Strategy Logic Guardrail Check
        context_str = str(sanitized_snapshot).lower()
        if not (user and user.is_admin):
            for key in self.PROHIBITED_KEYWORDS:
                if key in context_str:
                    self.audit_logger.log(
                        user_id=user_id,
                        event_type="AI_REQUEST_DENIED",
                        resource="ai_gateway",
                        action="build_context",
                        outcome="DENY",
                        details=f"Prohibited protected keyword '{key}' detected in context payload.",
                    )
                    return (
                        False,
                        None,
                        f"Access denied: protected content '{key}' detected and rejected.",
                    )

        # 4. Extract capability-specific minimal context
        permitted_symbol = (
            target_symbol.strip().upper()
            if target_symbol and isinstance(target_symbol, str)
            else sanitized_snapshot.get("market", {}).get("symbol")
        )

        permitted_signal: Optional[Dict[str, Any]] = None
        permitted_market: Optional[Dict[str, Any]] = None
        permitted_timeline: List[Dict[str, Any]] = []
        permitted_health: Optional[Dict[str, Any]] = None

        has_trade_setups_perm = user is not None and (
            user.has_permission(Permission.READ_TRADE_SETUPS) or user.is_admin
        )

        if capability == AICapability.EXPLAIN_SIGNAL:
            sig_dict = sanitized_snapshot.get("signal")
            if isinstance(sig_dict, dict) and sig_dict.get("action"):
                permitted_signal = {
                    "signal_id": sig_dict.get("signalId"),
                    "action": sig_dict.get("action"),
                    "symbol": permitted_symbol,
                    "timeframe": sig_dict.get("timeframe"),
                    "timestamp": sig_dict.get("timestamp"),
                    "confidence": sig_dict.get("confidence") if user and user.has_permission(Permission.READ_SIGNALS) else None,
                    "strategy_name": sig_dict.get("strategyName"),
                }
                # Include trade setup entry/SL/TP ONLY if user has READ_TRADE_SETUPS permission
                risk_dict = sanitized_snapshot.get("risk", {})
                if has_trade_setups_perm and isinstance(risk_dict, dict) and risk_dict.get("entry") is not None:
                    permitted_signal["trade_setup"] = {
                        "entry": risk_dict.get("entry"),
                        "stop_loss": risk_dict.get("stopLoss"),
                        "take_profits": risk_dict.get("takeProfits", []),
                    }

        elif capability == AICapability.SUMMARIZE_MARKET:
            mkt_dict = sanitized_snapshot.get("market", {})
            if isinstance(mkt_dict, dict):
                quote_dict = mkt_dict.get("quote") if isinstance(mkt_dict.get("quote"), dict) else {}
                permitted_market = {
                    "symbol": permitted_symbol or mkt_dict.get("symbol"),
                    "timeframe": mkt_dict.get("timeframe"),
                    "status": mkt_dict.get("status"),
                    "last_price": quote_dict.get("last") or quote_dict.get("mid"),
                    "change_24h": quote_dict.get("changePercent"),
                }

        elif capability == AICapability.SUMMARIZE_TIMELINE:
            activities = sanitized_snapshot.get("activity", [])
            if isinstance(activities, (list, tuple)):
                for item in activities[:10]:
                    if isinstance(item, dict):
                        permitted_timeline.append({
                            "timestamp": item.get("timestamp"),
                            "event": item.get("event"),
                            "details": SecretSanitizer.sanitize_string(str(item.get("details", ""))),
                        })

        elif capability == AICapability.EXPLAIN_HEALTH:
            mon_dict = sanitized_snapshot.get("monitoring", {})
            p1_dict = sanitized_snapshot.get("project1", {})
            permitted_health = {
                "platform_status": sanitized_snapshot.get("platform", {}).get("status", "ready"),
                "project1_connected": p1_dict.get("connected", False),
                "freshness": mon_dict.get("freshness"),
                "health": mon_dict.get("health"),
            }

        context = AllowedIntelligenceContext(
            context_id=f"ctx_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            capability=capability,
            timestamp=time.time(),
            permitted_symbol=permitted_symbol,
            permitted_signal=permitted_signal,
            permitted_market=permitted_market,
            permitted_timeline=tuple(permitted_timeline),
            permitted_health=permitted_health,
            is_sanitized=True,
            metadata={"source": "AIGatewayService", "role": user.role.value if user else "guest"},
        )

        return True, context, "Context built successfully"

    def process_ai_request(
        self,
        user: Optional[UserAuthorization],
        request: AIRequest,
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> AIResponse:
        """Process an AI request through authorization, context generation, and provider execution."""
        if not isinstance(request, AIRequest):
            raise ValueError("request must be an AIRequest instance")

        user_id = user.user_id if user else "anonymous"

        # Sanitize prompt query if provided (never log raw secrets)
        sanitized_query = (
            SecretSanitizer.sanitize_string(request.prompt_query)
            if request.prompt_query
            else None
        )

        # 1. Audit log AI_REQUEST
        self.audit_logger.log(
            user_id=user_id,
            event_type="AI_REQUEST",
            resource="ai_gateway",
            action=request.capability.value,
            outcome="ALLOW",
            details=f"Request ID {request.request_id} received for symbol {request.target_symbol or 'N/A'}",
        )

        # 2. Build allowed intelligence context
        success, context, reason = self.build_allowed_context(
            user=user,
            capability=request.capability,
            target_symbol=request.target_symbol,
            snapshot=snapshot,
        )

        if not success or context is None:
            self.audit_logger.log(
                user_id=user_id,
                event_type="AI_REQUEST_DENIED",
                resource="ai_gateway",
                action=request.capability.value,
                outcome="DENY",
                details=f"Request ID {request.request_id} denied: {reason}",
            )
            return AIResponse(
                request_id=request.request_id,
                status="PERMISSION_DENIED",
                capability=request.capability,
                provider_name=self._provider.provider_name(),
                content=f"Access denied: {reason}",
                created_at=time.time(),
                error_message=reason,
            )

        # 3. Check Provider Status
        provider_status = self._provider.get_status()
        self.audit_logger.log(
            user_id=user_id,
            event_type="AI_PROVIDER_STATUS",
            resource="ai_gateway",
            action="check_provider",
            outcome="ALLOW" if provider_status == AIProviderStatus.AVAILABLE else "DENY",
            details=f"Provider '{self._provider.provider_name()}' status: {provider_status.value}",
        )

        if provider_status != AIProviderStatus.AVAILABLE:
            self.audit_logger.log(
                user_id=user_id,
                event_type="AI_REQUEST_FAILED",
                resource="ai_gateway",
                action=request.capability.value,
                outcome="DENY",
                details=f"Request ID {request.request_id} failed: AI provider unavailable.",
            )
            return AIResponse(
                request_id=request.request_id,
                status="UNAVAILABLE",
                capability=request.capability,
                provider_name=self._provider.provider_name(),
                content="AI unavailable / provider not configured",
                created_at=time.time(),
                context_summary=context.to_dict(),
                error_message="AI provider is unavailable or not configured.",
            )

        # 4. Delegate to AI Provider Adapter
        try:
            response = self._provider.generate_explanation(context=context, request=request)
            self.audit_logger.log(
                user_id=user_id,
                event_type="AI_REQUEST_SUCCESS",
                resource="ai_gateway",
                action=request.capability.value,
                outcome="ALLOW",
                details=f"Explanation generated successfully by {self._provider.provider_name()}",
            )
            return response
        except Exception as err:
            err_msg = SecretSanitizer.sanitize_string(str(err))
            self.audit_logger.log(
                user_id=user_id,
                event_type="AI_REQUEST_FAILED",
                resource="ai_gateway",
                action=request.capability.value,
                outcome="DENY",
                details=f"Provider exception: {err_msg}",
            )
            return AIResponse(
                request_id=request.request_id,
                status="ERROR",
                capability=request.capability,
                provider_name=self._provider.provider_name(),
                content="An error occurred while processing the AI explanation.",
                created_at=time.time(),
                context_summary=context.to_dict(),
                error_message=err_msg,
            )

"""Comprehensive tests for AI Gateway boundary, domain models, provider adapters, authorization, context minimization, and security regressions.
"""

import time
import pytest

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
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.ai_gateway import AIGatewayService
from src.platform.services.security import AuditLogger, SecurityBoundaryService


class MockActiveAIProviderAdapter(AIProviderPort):
    """Mock AI Provider adapter for testing successful AI explanation generation."""

    def __init__(self, name: str = "MockGPT4Adapter") -> None:
        self._name = name

    def get_status(self) -> AIProviderStatus:
        return AIProviderStatus.AVAILABLE

    def provider_name(self) -> str:
        return self._name

    def generate_explanation(
        self, context: AllowedIntelligenceContext, request: AIRequest
    ) -> AIResponse:
        return AIResponse(
            request_id=request.request_id,
            status="SUCCESS",
            capability=request.capability,
            provider_name=self.provider_name(),
            content=f"Explanation generated for symbol {context.permitted_symbol}.",
            created_at=time.time(),
            context_summary=context.to_dict(),
        )


class MockFailingAIProviderAdapter(AIProviderPort):
    """Mock AI Provider adapter that raises an error during generation."""

    def get_status(self) -> AIProviderStatus:
        return AIProviderStatus.AVAILABLE

    def provider_name(self) -> str:
        return "MockFailingAdapter"

    def generate_explanation(
        self, context: AllowedIntelligenceContext, request: AIRequest
    ) -> AIResponse:
        raise RuntimeError("External AI service API key quota exceeded")


@pytest.fixture
def audit_logger() -> AuditLogger:
    return AuditLogger()


@pytest.fixture
def security_boundary(audit_logger: AuditLogger) -> SecurityBoundaryService:
    return SecurityBoundaryService(audit_logger=audit_logger)


@pytest.fixture
def ai_gateway(
    security_boundary: SecurityBoundaryService, audit_logger: AuditLogger
) -> AIGatewayService:
    return AIGatewayService(
        security_boundary=security_boundary,
        audit_logger=audit_logger,
        provider=UnavailableAIProviderAdapter(),
    )


@pytest.fixture
def standard_user() -> UserAuthorization:
    return UserAuthorization(
        user_id="usr_normal_1",
        auth_code="ac_normal_12345",
        role=UserRole.USER,
        permissions=(Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS),
    )


@pytest.fixture
def restricted_user() -> UserAuthorization:
    return UserAuthorization(
        user_id="usr_guest_1",
        auth_code="ac_guest_12345",
        role=UserRole.GUEST,
        permissions=(),
    )


@pytest.fixture
def admin_user() -> UserAuthorization:
    return UserAuthorization(
        user_id="usr_admin_1",
        auth_code="ac_admin_12345",
        role=UserRole.ADMIN,
        permissions=(Permission.ADMIN_ALL,),
    )


# --- 1. AI Domain Model Validation Tests ---


def test_ai_request_validation() -> None:
    req = AIRequest(
        request_id="req_001",
        user_id="usr_123",
        capability=AICapability.EXPLAIN_SIGNAL,
        target_symbol="xauusd",
    )
    assert req.request_id == "req_001"
    assert req.user_id == "usr_123"
    assert req.capability == AICapability.EXPLAIN_SIGNAL
    assert req.target_symbol == "XAUUSD"

    with pytest.raises(ValueError, match="request_id must be a non-empty string"):
        AIRequest(request_id="", user_id="u1", capability=AICapability.EXPLAIN_SIGNAL)

    with pytest.raises(ValueError, match="user_id must be a non-empty string"):
        AIRequest(request_id="r1", user_id=" ", capability=AICapability.EXPLAIN_SIGNAL)

    with pytest.raises(ValueError, match="invalid AICapability"):
        AIRequest(request_id="r1", user_id="u1", capability="invalid_cap")


def test_allowed_intelligence_context_validation() -> None:
    ctx = AllowedIntelligenceContext(
        context_id="ctx_001",
        user_id="usr_123",
        capability=AICapability.SUMMARIZE_MARKET,
        timestamp=1700000000.0,
        permitted_symbol="eurusd",
        permitted_market={"symbol": "EURUSD", "last_price": 1.0850},
    )
    assert ctx.context_id == "ctx_001"
    assert ctx.permitted_symbol == "EURUSD"
    assert ctx.is_sanitized is True
    summary = ctx.to_dict()
    assert summary["context_id"] == "ctx_001"
    assert summary["has_permitted_market"] is True


def test_ai_response_validation() -> None:
    resp = AIResponse(
        request_id="req_001",
        status="SUCCESS",
        capability=AICapability.EXPLAIN_HEALTH,
        provider_name="TestProvider",
        content="System is healthy.",
    )
    assert resp.status == "SUCCESS"
    assert resp.provider_name == "TestProvider"


# --- 2. Provider Port & Unavailable Adapter Tests ---


def test_unavailable_provider_adapter() -> None:
    adapter = UnavailableAIProviderAdapter()
    assert adapter.get_status() == AIProviderStatus.NOT_CONFIGURED
    assert adapter.provider_name() == "UnavailableAIProviderAdapter"

    ctx = AllowedIntelligenceContext(
        context_id="ctx_test",
        user_id="usr_1",
        capability=AICapability.EXPLAIN_SIGNAL,
        timestamp=time.time(),
    )
    req = AIRequest(
        request_id="req_test",
        user_id="usr_1",
        capability=AICapability.EXPLAIN_SIGNAL,
    )

    resp = adapter.generate_explanation(context=ctx, request=req)
    assert resp.status == "UNAVAILABLE"
    assert "AI unavailable / provider not configured" in resp.content
    assert resp.error_message == "No real AI provider adapter attached."


# --- 3. AIGatewayService Process & Authorization Tests ---


def test_process_ai_request_unavailable_provider(
    ai_gateway: AIGatewayService, standard_user: UserAuthorization
) -> None:
    req = AIRequest(
        request_id="req_unavail_1",
        user_id=standard_user.user_id,
        capability=AICapability.EXPLAIN_SIGNAL,
        target_symbol="XAUUSD",
    )
    snapshot = {
        "signal": {
            "signalId": "sig_001",
            "action": "BUY",
            "timeframe": "1h",
            "timestamp": "1700000000",
            "confidence": 0.9,
        },
        "market": {"symbol": "XAUUSD", "timeframe": "1h", "status": "connected"},
    }

    resp = ai_gateway.process_ai_request(user=standard_user, request=req, snapshot=snapshot)
    assert resp.status == "UNAVAILABLE"
    assert resp.content == "AI unavailable / provider not configured"
    assert resp.provider_name == "UnavailableAIProviderAdapter"


def test_process_ai_request_permission_denied(
    ai_gateway: AIGatewayService, restricted_user: UserAuthorization
) -> None:
    req = AIRequest(
        request_id="req_denied_1",
        user_id=restricted_user.user_id,
        capability=AICapability.EXPLAIN_SIGNAL,
        target_symbol="XAUUSD",
    )

    resp = ai_gateway.process_ai_request(user=restricted_user, request=req)
    assert resp.status == "PERMISSION_DENIED"
    assert "Access denied" in resp.content


def test_process_ai_request_success_with_active_provider(
    ai_gateway: AIGatewayService, standard_user: UserAuthorization, audit_logger: AuditLogger
) -> None:
    ai_gateway.set_provider(MockActiveAIProviderAdapter("MockGPT4Adapter"))

    req = AIRequest(
        request_id="req_success_1",
        user_id=standard_user.user_id,
        capability=AICapability.EXPLAIN_SIGNAL,
        target_symbol="XAUUSD",
    )
    snapshot = {
        "signal": {
            "signalId": "sig_100",
            "action": "BUY",
            "timeframe": "1h",
            "timestamp": "1700000000",
            "confidence": 0.85,
        },
        "market": {"symbol": "XAUUSD", "timeframe": "1h"},
    }

    resp = ai_gateway.process_ai_request(user=standard_user, request=req, snapshot=snapshot)
    assert resp.status == "SUCCESS"
    assert resp.provider_name == "MockGPT4Adapter"
    assert "Explanation generated for symbol XAUUSD" in resp.content

    # Verify audit events
    events = audit_logger.get_events(user_id=standard_user.user_id)
    event_types = [e.event_type for e in events]
    assert "AI_REQUEST" in event_types
    assert "AI_PROVIDER_STATUS" in event_types
    assert "AI_REQUEST_SUCCESS" in event_types


def test_process_ai_request_failure_handling(
    ai_gateway: AIGatewayService, standard_user: UserAuthorization, audit_logger: AuditLogger
) -> None:
    ai_gateway.set_provider(MockFailingAIProviderAdapter())

    req = AIRequest(
        request_id="req_fail_1",
        user_id=standard_user.user_id,
        capability=AICapability.EXPLAIN_SIGNAL,
        target_symbol="XAUUSD",
    )

    resp = ai_gateway.process_ai_request(user=standard_user, request=req)
    assert resp.status == "ERROR"
    assert "An error occurred" in resp.content
    assert "quota exceeded" in resp.error_message

    events = audit_logger.get_events(outcome="DENY")
    fail_events = [e for e in events if e.event_type == "AI_REQUEST_FAILED"]
    assert len(fail_events) > 0


# --- 4. Security Regression & Secret Sanitization Tests ---


def test_security_regression_proprietary_data_rejected(
    ai_gateway: AIGatewayService, standard_user: UserAuthorization, audit_logger: AuditLogger
) -> None:
    """Attempt to pass protected Project 1 strategy logic, indicator formulas, lab research, and credentials into AI context.

    Verify that protected content is rejected/stripped before reaching AI context.
    """
    ai_gateway.set_provider(MockActiveAIProviderAdapter())

    malicious_snapshot = {
        "signal": {
            "signalId": "sig_hack",
            "action": "BUY",
            "timeframe": "1h",
        },
        "best_strategies": [
            {"strategy_id": "secret_strat_1", "formula": "EMA_CROSS + MULTI_FACTOR_SECRET"}
        ],
        "indicator_logic": "def secret_indicator(): return 42",
        "sensitive_parameters": {"param_alpha": 0.0001, "param_beta": 99.9},
        "lab_secrets": "AES_KEY_LAB_998877",
        "credentials": "api_key=sk-live-1234567890secretkey",
    }

    success, context, reason = ai_gateway.build_allowed_context(
        user=standard_user,
        capability=AICapability.EXPLAIN_SIGNAL,
        target_symbol="XAUUSD",
        snapshot=malicious_snapshot,
    )

    assert success is False
    assert context is None
    assert "Access denied" in reason or "protected content" in reason

    # Verify audit event for denial
    denied_events = audit_logger.get_events(outcome="DENY")
    assert len(denied_events) > 0
    assert any("AI_REQUEST_DENIED" in e.event_type for e in denied_events)


def test_secret_sanitization_in_prompt_query(
    ai_gateway: AIGatewayService, standard_user: UserAuthorization, audit_logger: AuditLogger
) -> None:
    """Ensure user prompt queries with secrets like API keys or Bearer tokens are sanitized in audit logs."""
    ai_gateway.set_provider(MockActiveAIProviderAdapter())

    req = AIRequest(
        request_id="req_secret_query",
        user_id=standard_user.user_id,
        capability=AICapability.SUMMARIZE_MARKET,
        target_symbol="XAUUSD",
        prompt_query="Explain market using bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret and api_key=sk-1234567890",
    )

    resp = ai_gateway.process_ai_request(user=standard_user, request=req)
    assert resp.status == "SUCCESS"

    events = audit_logger.get_events(user_id=standard_user.user_id)
    for event in events:
        if event.details:
            assert "sk-1234567890" not in event.details
            assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in event.details


def test_context_minimization_trade_setup_permissions(
    ai_gateway: AIGatewayService
) -> None:
    """Verify context minimization excludes trade setups when user lacks READ_TRADE_SETUPS permission."""
    user_no_trade_setups = UserAuthorization(
        user_id="usr_no_setup",
        auth_code="ac_123",
        role=UserRole.USER,
        permissions=(Permission.READ_SIGNALS,),  # Missing Permission.READ_TRADE_SETUPS
    )

    snapshot = {
        "signal": {
            "signalId": "sig_200",
            "action": "BUY",
            "timeframe": "1h",
            "confidence": 0.9,
        },
        "risk": {
            "entry": 2650.0,
            "stopLoss": 2630.0,
            "takeProfits": [2680.0, 2700.0],
        },
    }

    success, context, _ = ai_gateway.build_allowed_context(
        user=user_no_trade_setups,
        capability=AICapability.EXPLAIN_SIGNAL,
        target_symbol="XAUUSD",
        snapshot=snapshot,
    )

    assert success is True
    assert context is not None
    assert context.permitted_signal is not None
    assert "trade_setup" not in context.permitted_signal

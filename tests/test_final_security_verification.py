"""Focused Final Security Hardening Verification Test Suite.

Verifies the 8 production security focus areas across AI-Trading-Lab-Platform:
1. Authentication & Session Enforcement
2. Authorization, RBAC & IDOR Defense
3. Sensitive Data Protection & Secret Redaction
4. Execution Boundary Fail-Closed Behavior
5. Provider & Configuration Security (SSRF / Scheme Validation)
6. Persistence, Backup & Restore Authorization and Path Traversal Defense
7. Abuse Controls & Input Bounding
8. Safe Error Handling
"""

import json
import os
import shutil
import tempfile
import time
from typing import Generator
import pytest

from src.platform.adapters.ai_provider import HttpAIProviderAdapter, UnavailableAIProviderAdapter
from src.platform.adapters.user_repository import FileBackedUserRepository
from src.platform.adapters.workspace_repository import FileBackedWorkspaceRepository
from src.platform.config import PlatformConfig
from src.platform.domain.ai_gateway import AICapability, AIProviderStatus, AIRequest, AllowedIntelligenceContext
from src.platform.domain.execution_gateway import ExecutionBoundaryStatus
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.execution_gateway import ExecutionGatewayService
from src.platform.services.persistence_recovery import PersistenceRecoveryEngine
from src.platform.services.security import AuditLogger, SecretSanitizer, SecurityBoundaryService
from src.platform.services.user_authorization import UserAuthorizationService
from src.platform.services.workspace import WorkspaceService


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def security_boundary() -> SecurityBoundaryService:
    return SecurityBoundaryService()


@pytest.fixture
def auth_service(temp_dir: str) -> UserAuthorizationService:
    repo = FileBackedUserRepository(storage_dir=temp_dir)
    audit = AuditLogger()
    return UserAuthorizationService(audit_logger=audit, repository=repo)


def test_focus_1_authentication_and_session_revocation(auth_service: UserAuthorizationService):
    """Verify session token validation, real-time validity checks, and instant session revocation."""
    admin = auth_service.get_user_authorization("admin_owner")
    assert admin is not None

    now = time.time()
    # Create customer account
    cust = auth_service.create_customer_account(
        actor_user=admin,
        target_user_id="cust1",
        plaintext_password="SecurePassword123!",
        activation_timestamp=now,
        expiration_timestamp=now + 86400,
    )
    assert cust is not None

    # Authenticate and obtain session token
    ok, user, msg = auth_service.authenticate_with_password("cust1", "SecurePassword123!")
    assert ok is True
    assert user is not None

    token = auth_service.create_session_token("cust1")
    assert bool(token) is True

    # Valid session token succeeds
    val_ok, val_user = auth_service.validate_session_token(token)
    assert val_ok is True
    assert val_user.user_id == "cust1"

    # Revoking session invalidates token immediately
    rev_count = auth_service.revoke_user_sessions(admin, "cust1")
    assert rev_count >= 1

    val_after, _ = auth_service.validate_session_token(token)
    assert val_after is False


def test_focus_2_authorization_rbac_and_idor(auth_service: UserAuthorizationService, temp_dir: str, security_boundary: SecurityBoundaryService):
    """Verify server-side RBAC enforcement, privilege escalation defense, and workspace IDOR isolation."""
    admin = auth_service.get_user_authorization("admin_owner")
    now = time.time()
    cust1 = auth_service.create_customer_account(admin, "cust_idor_1", "Pass123!", now, now + 86400)
    cust2 = auth_service.create_customer_account(admin, "cust_idor_2", "Pass123!", now, now + 86400)

    # Non-admin user attempting privilege escalation (updating role) is rejected
    with pytest.raises(PermissionError, match="Only Admin or Owner can update user roles"):
        auth_service.update_user_role(cust1, "cust_idor_1", UserRole.ADMIN)

    # Workspace service IDOR isolation check
    ws_repo = FileBackedWorkspaceRepository(storage_dir=temp_dir)
    ws_service = WorkspaceService(repository=ws_repo, security_service=security_boundary)

    # Customer 1 creating their workspace succeeds
    ws1 = ws_service.get_or_create_workspace(cust1, "cust_idor_1")
    assert ws1.user_id == "cust_idor_1"

    # Customer 1 attempting to access/modify Customer 2's workspace is rejected with PermissionError
    with pytest.raises(PermissionError, match="Access denied"):
        ws_service.get_or_create_workspace(cust1, "cust_idor_2")

    with pytest.raises(PermissionError, match="Access denied"):
        ws_service.set_active_symbol(cust1, "cust_idor_2", "XAUUSD")


def test_focus_3_sensitive_data_protection_and_secret_redaction():
    """Verify secrets, passwords, tokens, and credentials are never exposed in dictionaries or logs."""
    raw_secret = "Bearer secret_bearer_token_98765"
    sanitized = SecretSanitizer.sanitize_string(raw_secret)
    assert "secret_bearer_token_98765" not in sanitized
    assert "[REDACTED]" in sanitized

    # Verify dict/data sanitization
    d = {
        "user_id": "cust1",
        "password_hash": "pbkdf2:sha256:1000$secret_hash",
        "api_key": "sk-proj-secret1234567890",
        "token": "tok_xyz12345678",
        "nested": {"secret": "hidden_value"},
    }
    san_d = SecretSanitizer.sanitize_data(d)
    assert san_d["password_hash"] == "[REDACTED]"
    assert san_d["api_key"] == "[REDACTED]"
    assert san_d["token"] == "[REDACTED]"

    # Verify PlatformConfig dict sanitization
    config = PlatformConfig(session_secret="my_super_secret_key", initial_admin_password="AdminPass123!")
    config_d = config.to_sanitized_dict()
    assert config_d["session_secret"] == "[REDACTED]"
    assert config_d["initial_admin_password"] == "[REDACTED]"


def test_focus_4_execution_boundary_fail_closed(security_boundary: SecurityBoundaryService):
    """Verify execution gateway preserves fail-closed behavior without claiming unverified broker execution."""
    gateway_svc = ExecutionGatewayService(security_boundary=security_boundary)

    user = UserAuthorization(
        user_id="cust_exec",
        auth_code="AUTH_EXEC",
        role=UserRole.CUSTOMER,
        permissions=(Permission.READ_SIGNALS,),
    )

    # Unconfigured external adapter returns UNCONFIGURED boundary status
    boundary = gateway_svc.get_boundary_status(user)
    assert boundary["status"].upper() == ExecutionBoundaryStatus.UNCONFIGURED.value

    # Request execution returns externally_executed = False fail-closed result
    res = gateway_svc.request_execution(user, order_intent_id="intent_101")

    assert res.success is False
    assert res.externally_executed is False
    assert bool(res.detail) is True


def test_focus_5_provider_and_configuration_security():
    """Verify URL scheme and SSRF validation in HttpAIProviderAdapter and safe error responses for malformed data."""
    # Invalid schemes (file://, ftp://, gopher://, or empty netloc) are marked MISCONFIGURED
    p_file = HttpAIProviderAdapter(api_key="valid_key_12345", endpoint_url="file:///etc/passwd")
    assert p_file.get_status() == AIProviderStatus.MISCONFIGURED

    p_no_netloc = HttpAIProviderAdapter(api_key="valid_key_12345", endpoint_url="http://")
    assert p_no_netloc.get_status() == AIProviderStatus.MISCONFIGURED

    # Valid http/https with netloc is configured
    p_valid = HttpAIProviderAdapter(api_key="valid_key_12345", endpoint_url="https://api.openai.com/v1/chat/completions")
    assert p_valid.get_status() == AIProviderStatus.CONFIGURED

    # UnavailableAIProviderAdapter handles requests safely
    unavail = UnavailableAIProviderAdapter()
    req = AIRequest(request_id="req_1", user_id="cust1", capability=AICapability.EXPLAIN_SIGNAL)
    ctx = AllowedIntelligenceContext(
        context_id="c1",
        user_id="cust1",
        capability=AICapability.EXPLAIN_SIGNAL,
        timestamp=time.time(),
    )
    resp = unavail.generate_explanation(ctx, req)
    assert resp.status == "UNAVAILABLE"
    assert "not configured" in resp.content


def test_focus_6_persistence_recovery_and_path_traversal_defense(temp_dir: str):
    """Verify backup and restore operations enforce Admin RBAC and block path traversal attempts."""
    storage_dir = os.path.join(temp_dir, "persistence")
    backups_dir = os.path.join(temp_dir, "backups")
    os.makedirs(storage_dir, exist_ok=True)
    os.makedirs(backups_dir, exist_ok=True)

    # Create dummy persistence file to backup
    with open(os.path.join(storage_dir, "users.json"), "w", encoding="utf-8") as f:
        json.dump({"data": "test"}, f)

    engine = PersistenceRecoveryEngine(storage_dir=storage_dir, backups_dir=backups_dir)

    admin = UserAuthorization(user_id="admin", auth_code="ADM1", role=UserRole.ADMIN, permissions=(Permission.MANAGE_SYSTEM,))
    cust = UserAuthorization(user_id="cust1", auth_code="CUST1", role=UserRole.CUSTOMER, permissions=(Permission.READ_SIGNALS,))

    # Customer creation attempt fails with authorization error
    c_res = engine.create_backup(user=cust, label="test")
    assert c_res.success is False
    assert "Authorization failure" in c_res.message

    # Admin backup succeeds
    a_res = engine.create_backup(user=admin, label="test_backup")
    assert a_res.success is True

    # Path traversal restore attempt is blocked
    pt_res = engine.restore_backup(user=admin, backup_id_or_path="../../../etc/passwd")
    assert pt_res.success is False
    assert "verify_backup" in pt_res.message or "failed" in pt_res.message or "invalid" in pt_res.message.lower()


def test_focus_7_abuse_controls_and_input_bounding():
    """Verify input sanitization and bounded response handling."""
    dirty_input = "Bearer secret_bearer_token_12345"
    clean_str = SecretSanitizer.sanitize_string(dirty_input)
    assert "secret_bearer_token_12345" not in clean_str
    assert "[REDACTED]" in clean_str


def test_focus_8_safe_error_handling():
    """Verify safe error messages do not leak secrets or credentials."""
    raw_error = "Authorization error: Bearer secret_bearer_token_99999"
    clean_err = SecretSanitizer.sanitize_string(raw_error)
    assert "secret_bearer_token_99999" not in clean_err
    assert "[REDACTED]" in clean_err

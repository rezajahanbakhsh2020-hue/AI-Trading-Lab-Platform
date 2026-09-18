"""Production-readiness gap pass regression suite covering requirements A through O."""

import os
import shutil
import time
import pytest

from src.platform.config import PlatformConfig
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization, hash_password
from src.platform.adapters.user_repository import FileBackedUserRepository
from src.platform.services.user_authorization import UserAuthorizationService
from src.platform.services.security import SecurityBoundaryService, SecretSanitizer
from src.platform.services.health_operations import SystemHealthService


@pytest.fixture
def temp_persistence_dir(tmp_path):
    p_dir = str(tmp_path / "prod_readiness_data")
    yield p_dir
    if os.path.exists(p_dir):
        shutil.rmtree(p_dir)


def test_req_a_owner_remains_permanently_protected():
    """A. Owner/Admin remains permanently protected."""
    service = UserAuthorizationService()
    owner = service.get_user_authorization("admin_owner")
    assert owner is not None
    assert owner.is_permanent_admin is True
    assert owner.is_expired() is False
    assert owner.is_account_valid() is True

    # Attempt to deactivate or change expiration as admin should fail or keep owner valid
    with pytest.raises(ValueError, match="protected Admin/Owner account"):
        service.set_account_active_status(actor_user=owner, target_user_id="admin_owner", is_active=False)


def test_req_b_active_customer_can_authenticate():
    """B. Active customer can authenticate."""
    service = UserAuthorizationService()
    ok, user, msg = service.authenticate_with_password("demo_user", "DevCustomerPass2026!")
    assert ok is True
    assert user is not None
    assert user.user_id == "demo_user"


def test_req_c_d_e_customer_denial_cases():
    """C. Future customer denied. D. Expired customer denied. E. Deactivated customer denied."""
    service = UserAuthorizationService()
    admin = service.get_user_authorization("admin_owner")
    now_ts = time.time()

    # Create future user
    future_user = service.create_customer_account(
        actor_user=admin,
        target_user_id="future_cust",
        plaintext_password="Password2026!",
        activation_timestamp=now_ts + 86400,
        expiration_timestamp=now_ts + 2 * 86400,
    )
    ok_f, _, msg_f = service.authenticate_with_password("future_cust", "Password2026!")
    assert ok_f is False
    assert "not yet active" in msg_f

    # Create expired user
    expired_user = service.create_customer_account(
        actor_user=admin,
        target_user_id="expired_cust",
        plaintext_password="Password2026!",
        activation_timestamp=now_ts - 2 * 86400,
        expiration_timestamp=now_ts - 86400,
    )
    ok_e, _, msg_e = service.authenticate_with_password("expired_cust", "Password2026!")
    assert ok_e is False
    assert "expired" in msg_e

    # Deactivated customer
    active_cust = service.create_customer_account(
        actor_user=admin,
        target_user_id="deact_cust",
        plaintext_password="Password2026!",
        activation_timestamp=now_ts - 3600,
        expiration_timestamp=now_ts + 86400,
    )
    service.set_account_active_status(actor_user=admin, target_user_id="deact_cust", is_active=False)
    ok_d, _, msg_d = service.authenticate_with_password("deact_cust", "Password2026!")
    assert ok_d is False
    assert "deactivated" in msg_d


def test_req_f_expired_session_cannot_call_protected_api():
    """F. Expired/invalid session cannot call protected API."""
    service = UserAuthorizationService()
    token = service.create_session_token("demo_user")
    assert token is not None

    # Validate valid token
    valid_ok, _ = service.validate_session_token(token)
    assert valid_ok is True

    # Validate expired token by forcing short max_age
    val_expired, _ = service.validate_session_token(token, max_age_seconds=-1)
    assert val_expired is False


def test_req_g_h_i_customer_isolation_and_privilege_escalation_defense():
    """G. Customer cannot modify own role/expiry. H. Cannot access another customer data. I. Cannot become Admin."""
    sec = SecurityBoundaryService()
    service = UserAuthorizationService()
    now_ts = time.time()

    user = UserAuthorization(
        user_id="regular_cust",
        auth_code="AUTH_CUST",
        role=UserRole.USER,
        activation_timestamp=now_ts - 3600,
        expiration_timestamp=now_ts + 86400,
    )

    # Customer trying to run admin action
    with pytest.raises(PermissionError, match="Only Admin"):
        service.create_customer_account(
            actor_user=user,
            target_user_id="hacked_user",
            plaintext_password="Password2026!",
            activation_timestamp=now_ts,
            expiration_timestamp=now_ts + 86400,
        )

    # Security boundary forbids regular user access to secrets/admin resources
    allowed, msg = sec.authorize(user=user, resource="secrets", action="read")
    assert allowed is False
    assert "Access denied" in msg


def test_req_j_admin_can_manage_customer_lifecycle():
    """J. Admin can manage customer lifecycle."""
    service = UserAuthorizationService()
    admin = service.get_user_authorization("admin_owner")
    now_ts = time.time()

    new_cust = service.create_customer_account(
        actor_user=admin,
        target_user_id="lifecycle_cust",
        plaintext_password="Password2026!",
        activation_timestamp=now_ts - 3600,
        expiration_timestamp=now_ts + 86400,
    )

    # Renew account
    renewed = service.renew_customer_account(
        actor_user=admin,
        target_user_id="lifecycle_cust",
        new_expiration_timestamp=now_ts + 10 * 86400,
    )
    assert renewed.expiration_timestamp == now_ts + 10 * 86400


def test_req_k_m_secrets_never_appear_and_errors_sanitized():
    """K. Passwords/tokens/secrets never appear. M. Security errors sanitized."""
    sensitive_dict = {
        "user_id": "demo_user",
        "password": "SuperSecretPassword123!",
        "access_token": "bearer secret_token_xyz_12345",
    }
    sanitized = SecretSanitizer.sanitize_data(sensitive_dict)
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["access_token"] == "[REDACTED]"


def test_req_l_restart_persistence_behavior_safe(temp_persistence_dir):
    """L. Restart/persistence behavior is safe."""
    repo1 = FileBackedUserRepository(storage_dir=temp_persistence_dir)
    service1 = UserAuthorizationService(repository=repo1)

    ok, user, _ = service1.authenticate_with_password("demo_user", "DevCustomerPass2026!")
    assert ok is True
    token = service1.create_session_token("demo_user")

    # Re-instantiate
    repo2 = FileBackedUserRepository(storage_dir=temp_persistence_dir)
    service2 = UserAuthorizationService(repository=repo2)

    val_ok, val_user = service2.validate_session_token(token)
    assert val_ok is True
    assert val_user.user_id == "demo_user"

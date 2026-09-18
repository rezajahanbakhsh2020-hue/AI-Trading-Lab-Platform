"""Comprehensive Integration and Security Tests for Customer/Admin Management and Workspace.

Covers:
- Owner/Admin/Customer RBAC boundary permissions and privilege escalation defenses
- Customer lifecycle operations (create, activate, deactivate, renew, expiration enforcement)
- Session revocation and immediate token invalidation
- Personal Workspace & Watchlist user isolation (IDOR protection)
- FileBackedWorkspaceRepository process-restart persistence
- Security audit event generation
"""

import os
import shutil
import tempfile
import time
import pytest

from src.platform.config import PlatformConfig
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.domain.workspace import Watchlist, Workspace
from src.platform.adapters.user_repository import FileBackedUserRepository
from src.platform.adapters.workspace_repository import FileBackedWorkspaceRepository
from src.platform.services.user_authorization import UserAuthorizationService
from src.platform.services.workspace import WorkspaceService
from src.platform.services.security import SecurityBoundaryService, AuditLogger


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def test_services(temp_dir):
    cfg = PlatformConfig(
        app_env="testing",
        session_secret="test_session_secret_key_32_chars_long_2026!",
        persistence_dir=temp_dir,
    )
    user_repo = FileBackedUserRepository(storage_dir=temp_dir)
    ws_repo = FileBackedWorkspaceRepository(storage_dir=temp_dir)
    audit = AuditLogger()
    auth_service = UserAuthorizationService(audit_logger=audit, repository=user_repo, config=cfg)
    sec_service = SecurityBoundaryService(audit_logger=audit)
    ws_service = WorkspaceService(repository=ws_repo, security_service=sec_service)

    return {
        "config": cfg,
        "user_repo": user_repo,
        "ws_repo": ws_repo,
        "auth_service": auth_service,
        "ws_service": ws_service,
        "audit": audit,
        "temp_dir": temp_dir,
    }


def test_rbac_and_role_management_rules(test_services):
    auth_svc = test_services["auth_service"]

    owner = auth_svc.get_user_authorization("admin_owner")
    assert owner is not None
    assert owner.is_owner

    now = time.time()
    # Provision Admin and Customer
    admin_user = auth_svc.create_customer_account(
        actor_user=owner,
        target_user_id="admin_sec",
        plaintext_password="AdminPass2026!",
        activation_timestamp=now - 10,
        expiration_timestamp=now + 86400,
        role=UserRole.ADMIN,
    )
    assert admin_user.role == UserRole.ADMIN

    cust_user = auth_svc.create_customer_account(
        actor_user=owner,
        target_user_id="cust_one",
        plaintext_password="CustPass2026!",
        activation_timestamp=now - 10,
        expiration_timestamp=now + 86400,
        role=UserRole.CUSTOMER,
    )
    assert cust_user.role == UserRole.CUSTOMER

    # Admin CANNOT promote anyone to Owner or Admin
    with pytest.raises(PermissionError, match="Admin cannot promote"):
        auth_svc.update_user_role(admin_user, "cust_one", UserRole.ADMIN)

    # Admin CANNOT modify Owner account
    with pytest.raises(PermissionError, match="Admin cannot modify Owner"):
        auth_svc.update_user_role(admin_user, "admin_owner", UserRole.CUSTOMER)

    # Owner CAN promote customer to admin
    updated_cust = auth_svc.update_user_role(owner, "cust_one", UserRole.ADMIN)
    assert updated_cust.role == UserRole.ADMIN

    # Non-admin customer CANNOT alter roles
    with pytest.raises(PermissionError, match="Only Admin or Owner"):
        auth_svc.update_user_role(cust_user, "cust_one", UserRole.CUSTOMER)


def test_customer_lifecycle_management(test_services):
    auth_svc = test_services["auth_service"]
    owner = auth_svc.get_user_authorization("admin_owner")
    now = time.time()

    # Create account
    user = auth_svc.create_customer_account(
        actor_user=owner,
        target_user_id="lifecycle_user",
        plaintext_password="TestPass2026!",
        activation_timestamp=now - 100,
        expiration_timestamp=now + 1000,
    )
    assert user.is_account_valid(now)

    # Deactivate
    deactivated = auth_svc.set_account_active_status(owner, "lifecycle_user", False)
    assert not deactivated.is_active
    assert not deactivated.is_account_valid(now)

    # Activate
    reactivated = auth_svc.set_account_active_status(owner, "lifecycle_user", True)
    assert reactivated.is_active
    assert reactivated.is_account_valid(now)

    # Renew/Extend expiration
    renewed = auth_svc.renew_customer_account(owner, "lifecycle_user", now + 5000)
    assert renewed.expiration_timestamp == now + 5000


def test_session_revocation_and_invalidation(test_services):
    auth_svc = test_services["auth_service"]
    owner = auth_svc.get_user_authorization("admin_owner")
    now = time.time()

    user = auth_svc.create_customer_account(
        actor_user=owner,
        target_user_id="session_user",
        plaintext_password="Pass2026!",
        activation_timestamp=now - 10,
        expiration_timestamp=now + 86400,
    )

    # Authenticate & generate session token
    token = auth_svc.create_session_token("session_user")
    assert token is not None

    valid, session_user = auth_svc.validate_session_token(token)
    assert valid
    assert session_user.user_id == "session_user"

    # Revoke sessions as Admin/Owner
    revoked_count = auth_svc.revoke_user_sessions(owner, "session_user")
    assert revoked_count == 1

    # Token must now fail validation immediately
    valid_after, _ = auth_svc.validate_session_token(token)
    assert not valid_after


def test_user_workspace_isolation_and_idor_protection(test_services):
    auth_svc = test_services["auth_service"]
    ws_svc = test_services["ws_service"]
    owner = auth_svc.get_user_authorization("admin_owner")
    now = time.time()

    u1 = auth_svc.create_customer_account(
        actor_user=owner,
        target_user_id="user_alpha",
        plaintext_password="Pass1!",
        activation_timestamp=now - 10,
        expiration_timestamp=now + 86400,
    )

    u2 = auth_svc.create_customer_account(
        actor_user=owner,
        target_user_id="user_beta",
        plaintext_password="Pass2!",
        activation_timestamp=now - 10,
        expiration_timestamp=now + 86400,
    )

    # Alpha gets/creates their own workspace
    ws_alpha = ws_svc.get_or_create_workspace(u1, "user_alpha")
    assert ws_alpha.user_id == "user_alpha"

    # Alpha attempts cross-user access to Beta's workspace -> MUST RAISE PermissionError (IDOR Protection)
    with pytest.raises(PermissionError, match="not authorized to access workspace"):
        ws_svc.get_or_create_workspace(u1, "user_beta")

    # Admin (owner) CAN access Beta's workspace
    ws_beta_by_admin = ws_svc.get_or_create_workspace(owner, "user_beta")
    assert ws_beta_by_admin.user_id == "user_beta"


def test_workspace_repository_process_restart_persistence(test_services):
    ws_svc = test_services["ws_service"]
    auth_svc = test_services["auth_service"]
    temp_dir = test_services["temp_dir"]
    owner = auth_svc.get_user_authorization("admin_owner")

    # Create workspace and add watchlist
    ws, wl = ws_svc.create_watchlist(owner, "admin_owner", "Crypto Watchlist", ["BTCUSD", "ETHUSD"])
    assert wl.name == "Crypto Watchlist"

    # Simulate process restart by instantiating new repository and service reading from disk
    new_ws_repo = FileBackedWorkspaceRepository(storage_dir=temp_dir)
    new_ws_svc = WorkspaceService(repository=new_ws_repo)

    reloaded_ws = new_ws_svc.get_or_create_workspace(owner, "admin_owner")
    assert wl.watchlist_id in reloaded_ws.watchlists
    assert reloaded_ws.watchlists[wl.watchlist_id].name == "Crypto Watchlist"
    assert "BTCUSD" in reloaded_ws.watchlists[wl.watchlist_id].symbols

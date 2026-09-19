"""Focused end-to-end integration and security test suite for Identity, User Lifecycle, and Account Recovery."""

import json
import os
import time
import pytest

from src.platform.config import PlatformConfig
from src.platform.domain.security import Permission, UserRole
from src.platform.domain.user_authorization import AccountStatus, UserAuthorization
from src.platform.services.user_authorization import UserAuthorizationService
from src.platform.adapters.user_repository import FileBackedUserRepository


def test_user_account_lifecycle_transitions(tmp_path):
    storage_dir = str(tmp_path / "data")
    repo = FileBackedUserRepository(storage_dir=storage_dir)
    service = UserAuthorizationService(repository=repo)

    admin = service.get_user_authorization("admin_owner")
    assert admin is not None
    assert admin.account_status == AccountStatus.PERMANENT_ADMIN

    now_ts = time.time()
    created = service.create_customer_account(
        actor_user=admin,
        target_user_id="lifecycle_user",
        plaintext_password="Password123!",
        activation_timestamp=now_ts - 100,
        expiration_timestamp=now_ts + 3600,
        allowed_symbols=("XAUUSD",),
    )
    assert created.user_id == "lifecycle_user"
    assert created.account_status == AccountStatus.ACTIVE
    assert created.is_account_valid() is True

    # Authenticate and obtain session
    ok, user, _ = service.authenticate_with_password("lifecycle_user", "Password123!")
    assert ok is True
    session_token = service.create_session_token("lifecycle_user")
    assert session_token is not None

    valid, sess_user = service.validate_session_token(session_token)
    assert valid is True
    assert sess_user.user_id == "lifecycle_user"

    # Deactivate account -> session should be immediately invalidated
    deactivated = service.deactivate_user_account(admin, "lifecycle_user")
    assert deactivated.is_active is False
    assert deactivated.account_status == AccountStatus.INACTIVE

    valid_after_deact, _ = service.validate_session_token(session_token)
    assert valid_after_deact is False

    # Deactivated account cannot authenticate
    ok_login, _, msg = service.authenticate_with_password("lifecycle_user", "Password123!")
    assert ok_login is False
    assert "deactivated" in msg.lower()

    # Reactivate account
    reactivated = service.reactivate_user_account(admin, "lifecycle_user")
    assert reactivated.is_active is True
    assert reactivated.account_status == AccountStatus.ACTIVE

    ok_login_react, user_react, _ = service.authenticate_with_password("lifecycle_user", "Password123!")
    assert ok_login_react is True


def test_owner_admin_customer_role_protection(tmp_path):
    repo = FileBackedUserRepository(storage_dir=str(tmp_path / "data"))
    service = UserAuthorizationService(repository=repo)

    owner = service.get_user_authorization("admin_owner")
    now_ts = time.time()

    # Create an admin user and a customer user
    admin_acc = service.create_customer_account(
        actor_user=owner,
        target_user_id="admin_two",
        plaintext_password="AdminPass123!",
        activation_timestamp=now_ts - 10,
        expiration_timestamp=now_ts + 3600,
        role=UserRole.ADMIN,
    )

    cust_acc = service.create_customer_account(
        actor_user=owner,
        target_user_id="customer_one",
        plaintext_password="CustPass123!",
        activation_timestamp=now_ts - 10,
        expiration_timestamp=now_ts + 3600,
        role=UserRole.CUSTOMER,
    )

    # Customer cannot modify role or perform admin operations
    with pytest.raises(PermissionError):
        service.update_user_role(cust_acc, "admin_two", UserRole.CUSTOMER)

    with pytest.raises(PermissionError):
        service.deactivate_user_account(cust_acc, "admin_two")

    # Admin cannot demote Owner
    with pytest.raises(PermissionError):
        service.update_user_role(admin_acc, "admin_owner", UserRole.CUSTOMER)

    # Admin cannot promote anyone to Owner
    with pytest.raises(PermissionError):
        service.update_user_role(admin_acc, "customer_one", UserRole.OWNER)

    # Owner can change role safely
    updated_role = service.update_user_role(owner, "customer_one", UserRole.ADMIN)
    assert updated_role.role == UserRole.ADMIN


def test_password_recovery_flow_single_use_and_honest_delivery(tmp_path):
    repo = FileBackedUserRepository(storage_dir=str(tmp_path / "data"))
    service = UserAuthorizationService(repository=repo)

    admin = service.get_user_authorization("admin_owner")
    now_ts = time.time()

    user = service.create_customer_account(
        actor_user=admin,
        target_user_id="recovery_user",
        plaintext_password="OldPassword123!",
        activation_timestamp=now_ts - 10,
        expiration_timestamp=now_ts + 3600,
    )

    # Authenticate and obtain active session token
    ok, _, _ = service.authenticate_with_password("recovery_user", "OldPassword123!")
    assert ok is True
    token = service.create_session_token("recovery_user")
    assert token is not None

    # Initiate recovery request
    req_res = service.request_password_recovery("recovery_user", "recovery@example.com")
    assert req_res["success"] is True
    assert req_res["delivery_status"] == "NOT_CONFIGURED"
    assert "Not Configured" in req_res["delivery_detail"]

    rec_token = req_res["recovery_token"]
    assert rec_token is not None and rec_token.startswith("rec_")

    # Non-existent user recovery request returns generic message (enumeration resistance)
    ghost_res = service.request_password_recovery("ghost_user", "ghost@example.com")
    assert ghost_res["success"] is True
    assert ghost_res["recovery_token"] is None
    assert ghost_res["message"] == req_res["message"]

    # Invalid token reset fails
    reset_fail, fail_msg = service.reset_password_with_recovery_token("recovery_user", "invalid_token", "NewPass123!")
    assert reset_fail is False
    assert "invalid" in fail_msg.lower()

    # Valid token reset succeeds and revokes pre-existing sessions
    reset_ok, ok_msg = service.reset_password_with_recovery_token("recovery_user", rec_token, "NewPassword123!")
    assert reset_ok is True
    assert "successful" in ok_msg.lower()

    # Session prior to reset is now revoked
    valid_old_sess, _ = service.validate_session_token(token)
    assert valid_old_sess is False

    # Old password no longer works, new password works
    old_login, _, _ = service.authenticate_with_password("recovery_user", "OldPassword123!")
    assert old_login is False

    new_login, _, _ = service.authenticate_with_password("recovery_user", "NewPassword123!")
    assert new_login is True

    # Replay recovery token fails (single-use token enforcement)
    replay_reset, replay_msg = service.reset_password_with_recovery_token("recovery_user", rec_token, "AnotherPass123!")
    assert replay_reset is False
    assert "no active recovery request" in replay_msg.lower()


def test_persistence_restart_recovery_and_lifecycle(tmp_path):
    storage_dir = str(tmp_path / "data")

    # Step 1: Initialize service & create user
    repo1 = FileBackedUserRepository(storage_dir=storage_dir)
    service1 = UserAuthorizationService(repository=repo1)
    admin1 = service1.get_user_authorization("admin_owner")

    now_ts = time.time()
    service1.create_customer_account(
        actor_user=admin1,
        target_user_id="persisted_user",
        plaintext_password="PersistPass123!",
        activation_timestamp=now_ts - 10,
        expiration_timestamp=now_ts + 7200,
    )
    service1.request_password_recovery("persisted_user", "persist@example.com")

    # Step 2: Restart service from persistent store
    repo2 = FileBackedUserRepository(storage_dir=storage_dir)
    service2 = UserAuthorizationService(repository=repo2)

    loaded_user = service2.get_user_authorization("persisted_user")
    assert loaded_user is not None
    assert loaded_user.recovery_email == "persist@example.com"
    assert loaded_user.recovery_token_hash is not None

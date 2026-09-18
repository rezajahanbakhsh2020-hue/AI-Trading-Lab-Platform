"""Tests for FileBackedUserRepository and UserAuthorizationService persistence functionality."""

import os
import shutil
import time
import pytest

from src.platform.adapters.user_repository import FileBackedUserRepository
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.user_authorization import UserAuthorizationService


@pytest.fixture
def temp_storage_dir(tmp_path):
    storage_dir = str(tmp_path / "test_data")
    yield storage_dir
    if os.path.exists(storage_dir):
        shutil.rmtree(storage_dir)


def test_user_repository_persistence(temp_storage_dir):
    repo1 = FileBackedUserRepository(storage_dir=temp_storage_dir)
    service1 = UserAuthorizationService(repository=repo1)

    # Authenticate and create session
    ok, user, msg = service1.authenticate_with_password("demo_user", "CustomerPass2026!")
    assert ok
    assert user is not None

    token = service1.create_session_token("demo_user")
    assert token is not None

    # Instantiate new service instance pointing to same repository directory
    repo2 = FileBackedUserRepository(storage_dir=temp_storage_dir)
    service2 = UserAuthorizationService(repository=repo2)

    # Validate session from persisted state
    val_ok, val_user = service2.validate_session_token(token)
    assert val_ok
    assert val_user is not None
    assert val_user.user_id == "demo_user"


def test_user_repository_revoke_persistence(temp_storage_dir):
    repo = FileBackedUserRepository(storage_dir=temp_storage_dir)
    service = UserAuthorizationService(repository=repo)

    token = service.create_session_token("admin_owner")
    assert token is not None

    service.revoke_session_token(token)

    repo_reloaded = FileBackedUserRepository(storage_dir=temp_storage_dir)
    service_reloaded = UserAuthorizationService(repository=repo_reloaded)

    val_ok, _ = service_reloaded.validate_session_token(token)
    assert not val_ok

"""Focused production tests for Owner/Admin identity, real transactional email delivery,
and account recovery & security notification integrations.
"""

import os
import time
import pytest

from src.platform.config import PlatformConfig
from src.platform.domain.notification import (
    NotificationCategory,
    NotificationEvent,
    NotificationSeverity,
)
from src.platform.domain.security import UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.integrations.email_delivery import EmailDeliveryPort, EmailDeliveryResult
from src.platform.providers.email_delivery import (
    DisabledEmailDeliveryAdapter,
    MockEmailDeliveryAdapter,
    SmtpEmailDeliveryAdapter,
)
from src.platform.services.email_delivery import EmailDeliveryService
from src.platform.services.notification_delivery import NotificationDeliveryService
from src.platform.services.security import AuditLogger, SecretSanitizer
from src.platform.services.user_authorization import UserAuthorizationService, hash_token


def test_platform_config_owner_and_email_fields():
    """Verify PlatformConfig properly loads and redacts owner identity and email settings."""
    cfg = PlatformConfig(
        app_env="development",
        owner_user_id="custom_owner",
        owner_email="owner@domain.local",
        email_provider="smtp",
        email_host="smtp.domain.local",
        email_port=587,
        email_username="smtp_user",
        email_password="super_secret_smtp_password",
        email_from="noreply@domain.local",
    )

    assert cfg.owner_user_id == "custom_owner"
    assert cfg.owner_email == "owner@domain.local"
    assert cfg.email_provider == "smtp"

    sanitized = cfg.to_sanitized_dict()
    assert sanitized["email_password"] == "[REDACTED]"
    assert sanitized["session_secret"] == "[REDACTED]"
    assert sanitized["owner_user_id"] == "custom_owner"
    assert sanitized["owner_email"] == "owner@domain.local"


def test_owner_bootstrap_with_custom_config():
    """Verify owner bootstrap initializes configured owner user ID and recovery email."""
    cfg = PlatformConfig(
        app_env="development",
        owner_user_id="prod_owner_main",
        owner_email="primary_owner@company.com",
        initial_admin_password="ProductionOwnerKey2026!",
    )

    auth_svc = UserAuthorizationService(config=cfg)
    owner = auth_svc.get_user_authorization("prod_owner_main")

    assert owner is not None
    assert owner.user_id == "prod_owner_main"
    assert owner.role == UserRole.OWNER
    assert owner.is_permanent_admin is True
    assert owner.recovery_email == "primary_owner@company.com"
    assert owner.verify_password("ProductionOwnerKey2026!") is True


def test_configured_owner_recovery_email_propagation_and_status(monkeypatch):
    """Verify designated owner recovery email Reza.jahanbakhsh2020@gmail.com is loaded, normalized, and propagated to Owner account."""
    monkeypatch.setenv("OWNER_EMAIL", "Reza.jahanbakhsh2020@gmail.com")
    monkeypatch.setenv("RECOVERY_EMAIL", "Reza.jahanbakhsh2020@gmail.com")

    cfg = PlatformConfig.load_from_env()
    assert cfg.owner_email == "reza.jahanbakhsh2020@gmail.com"
    assert cfg.recovery_email == "reza.jahanbakhsh2020@gmail.com"

    auth_svc = UserAuthorizationService(config=cfg)
    owner = auth_svc.get_user_authorization(cfg.owner_user_id)

    assert owner is not None
    assert owner.recovery_email == "reza.jahanbakhsh2020@gmail.com"

    # Password recovery request recognizes configured owner recipient
    res = auth_svc.request_password_recovery(owner.user_id, "Reza.jahanbakhsh2020@gmail.com")
    assert res["success"] is True
    # Honest status reporting when external SMTP credentials are absent
    assert res["delivery_status"] == "NOT_CONFIGURED"
    assert res["recovery_token"] is not None


def test_email_delivery_adapters():
    """Verify DisabledEmailDeliveryAdapter and MockEmailDeliveryAdapter behaviors."""
    disabled_adapter = DisabledEmailDeliveryAdapter("Not configured in test.")
    res_disabled = disabled_adapter.send_email(
        to_email="test@domain.com",
        subject="Test Subject",
        body_text="Test Body",
    )

    assert res_disabled.success is False
    assert res_disabled.status_code == "NOT_CONFIGURED"
    assert res_disabled.externally_delivered is False

    mock_adapter = MockEmailDeliveryAdapter(configured=True, should_succeed=True)
    res_mock = mock_adapter.send_email(
        to_email="customer@domain.com",
        subject="Welcome",
        body_text="Hello Customer",
    )

    assert res_mock.success is True
    assert res_mock.status_code == "SENT"
    assert res_mock.externally_delivered is True
    assert len(mock_adapter.sent_messages) == 1
    assert mock_adapter.sent_messages[0]["to_email"] == "customer@domain.com"


def test_recovery_flow_with_unconfigured_email():
    """Verify recovery request when email is not configured exposes NOT_CONFIGURED state safely."""
    auth_svc = UserAuthorizationService()
    res = auth_svc.request_password_recovery("demo_user", "dev_customer@platform.local")

    assert res["success"] is True
    assert res["delivery_status"] == "NOT_CONFIGURED"
    # Token returned for manual presentation when email is NOT_CONFIGURED
    assert res["recovery_token"] is not None
    assert res["recovery_token"].startswith("rec_")


def test_recovery_flow_with_configured_email_omits_token_from_response():
    """Verify recovery request when email is configured sends recovery email and omits raw token from API response."""
    cfg = PlatformConfig(
        app_env="development",
        email_provider="mock",
        email_from="auth@platform.local",
    )
    email_svc = EmailDeliveryService(config=cfg)
    auth_svc = UserAuthorizationService(config=cfg, email_service=email_svc)

    # Register user with recovery email
    user = auth_svc.get_user_authorization("demo_user")
    updated_user = UserAuthorization(
        user_id=user.user_id,
        auth_code=user.auth_code,
        role=user.role,
        recovery_email="customer@domain.com",
        password_hash=user.password_hash,
        salt=user.salt,
    )
    auth_svc.register_user(updated_user)

    res = auth_svc.request_password_recovery("demo_user", "customer@domain.com")

    assert res["success"] is True
    assert res["delivery_status"] == "SENT"
    # Token must be omitted from public API response when delivered externally
    assert res["recovery_token"] is None

    mock_adapter = email_svc.adapter
    assert isinstance(mock_adapter, MockEmailDeliveryAdapter)
    assert len(mock_adapter.sent_messages) == 1
    sent_msg = mock_adapter.sent_messages[0]
    assert sent_msg["to_email"] == "customer@domain.com"
    assert "Password Recovery Request" in sent_msg["subject"]
    assert "rec_" in sent_msg["body_text"]


def test_recovery_password_reset_and_session_revocation():
    """Verify password reset via recovery token revokes active user sessions."""
    cfg = PlatformConfig(
        app_env="development",
        email_provider="mock",
    )
    email_svc = EmailDeliveryService(config=cfg)
    auth_svc = UserAuthorizationService(config=cfg, email_service=email_svc)

    user = auth_svc.get_user_authorization("demo_user")
    updated_user = UserAuthorization(
        user_id=user.user_id,
        auth_code=user.auth_code,
        role=user.role,
        recovery_email="user@domain.com",
        password_hash=user.password_hash,
        salt=user.salt,
    )
    auth_svc.register_user(updated_user)

    # Create active session
    session_token = auth_svc.create_session_token("demo_user")
    assert session_token is not None
    valid, s_user = auth_svc.validate_session_token(session_token)
    assert valid is True

    # Request recovery
    auth_svc.request_password_recovery("demo_user", "user@domain.com")

    # Extract single-use token from mock email message
    mock_adapter = email_svc.adapter
    sent_text = mock_adapter.sent_messages[0]["body_text"]
    token_line = [line for line in sent_text.splitlines() if "rec_" in line][0]
    recovery_token = [part for part in token_line.split() if part.startswith("rec_")][0].strip()

    # Perform reset
    reset_ok, msg = auth_svc.reset_password_with_recovery_token("demo_user", recovery_token, "NewPassword2026!")
    assert reset_ok is True

    # Confirm session token was revoked post-reset
    valid_after, _ = auth_svc.validate_session_token(session_token)
    assert valid_after is False

    # Confirm login works with new password
    auth_ok, new_u, _ = auth_svc.authenticate_with_password("demo_user", "NewPassword2026!")
    assert auth_ok is True


def test_security_notifications_dispatched_on_account_lifecycle_changes():
    """Verify security notification emails are dispatched when account status or role changes."""
    cfg = PlatformConfig(app_env="development", email_provider="mock")
    email_svc = EmailDeliveryService(config=cfg)
    auth_svc = UserAuthorizationService(config=cfg, email_service=email_svc)

    owner = auth_svc.get_user_authorization("admin_owner")
    target = auth_svc.get_user_authorization("demo_user")

    # Give target a recovery email
    updated_target = UserAuthorization(
        user_id=target.user_id,
        auth_code=target.auth_code,
        role=target.role,
        recovery_email="target@domain.com",
        password_hash=target.password_hash,
        salt=target.salt,
    )
    auth_svc.register_user(updated_target)

    mock_adapter = email_svc.adapter
    mock_adapter.sent_messages.clear()

    # Deactivate target
    auth_svc.deactivate_user_account(owner, "demo_user")

    assert len(mock_adapter.sent_messages) == 1
    msg1 = mock_adapter.sent_messages[0]
    assert msg1["to_email"] == "target@domain.com"
    assert "Deactivated" in msg1["subject"]


def test_secret_redaction_and_enumeration_defense():
    """Verify secret sanitizer redacts secrets and recovery flow is enumeration resistant."""
    dirty_dict = {
        "password": "MySecretPassword123",
        "api_key": "sk-1234567890abcdef",
        "recovery_token": "rec_abcdef123456",
        "normal_field": "public_data",
    }
    sanitized = SecretSanitizer.sanitize_data(dirty_dict)
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["recovery_token"] == "[REDACTED]"
    assert sanitized["normal_field"] == "public_data"

    auth_svc = UserAuthorizationService()
    res_fake = auth_svc.request_password_recovery("non_existent_user_999", "fake@domain.com")
    res_real = auth_svc.request_password_recovery("admin_owner", "wrong_email@domain.com")

    # Generic enumeration-resistant message
    assert res_fake["message"] == res_real["message"]
    assert res_fake["success"] is True
    assert res_real["success"] is True


def test_server_email_service_wiring_integration():
    """Verify create_server wires EmailDeliveryService into UserAuthorizationService and NotificationDeliveryService."""
    from src.platform.server import create_server
    cfg = PlatformConfig(
        app_env="development",
        email_provider="mock",
        email_from="server_auth@platform.local",
    )

    server = create_server(host="127.0.0.1", port=0, config=cfg)
    handler_cls = server.RequestHandlerClass

    assert handler_cls.server_user_auth_service._email_service is not None
    assert handler_cls.notification_delivery_service._email_service is not None

    # Test recovery request through server user auth service
    res = handler_cls.server_user_auth_service.request_password_recovery(
        "admin_owner", "reza.jahanbakhsh2020@gmail.com"
    )
    assert res["success"] is True
    assert res["delivery_status"] == "SENT"
    assert res["recovery_token"] is None  # Omitted when sent via mock adapter

    mock_adapter = handler_cls.server_user_auth_service._email_service.adapter
    assert len(mock_adapter.sent_messages) == 1
    assert mock_adapter.sent_messages[0]["to_email"] == "reza.jahanbakhsh2020@gmail.com"

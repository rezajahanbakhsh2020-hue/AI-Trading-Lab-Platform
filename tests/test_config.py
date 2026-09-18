"""Tests for PlatformConfig runtime environment settings and production security contract."""

import os
import pytest
from src.platform.config import PlatformConfig


def test_platform_config_defaults():
    config = PlatformConfig()
    assert config.app_env == "development"
    assert not config.is_production
    assert config.is_origin_allowed("http://localhost:5173")
    assert not config.is_origin_allowed("http://malicious-site.com")
    sanitized = config.to_sanitized_dict()
    assert sanitized["session_secret"] == "[REDACTED]"


def test_platform_config_production_fail_closed():
    with pytest.raises(ValueError, match="SESSION_SECRET must be explicitly set"):
        PlatformConfig(app_env="production", session_secret="dev_session_secret_key_change_in_production_2026")


def test_platform_config_production_valid():
    valid_secret = "a_very_long_secure_production_secret_key_32bytes"
    config = PlatformConfig(app_env="production", session_secret=valid_secret)
    assert config.is_production
    headers = config.get_security_headers()
    assert "Strict-Transport-Security" in headers
    assert headers["X-Frame-Options"] == "DENY"


def test_platform_config_load_from_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.mydomain.com, https://admin.mydomain.com")
    monkeypatch.setenv("SESSION_SECRET", "custom_dev_secret_key_for_testing_12345")
    monkeypatch.setenv("RECOVERY_EMAIL", "owner@mydomain.com")

    config = PlatformConfig.load_from_env()
    assert config.app_env == "development"
    assert config.recovery_email == "owner@mydomain.com"
    assert config.is_origin_allowed("https://app.mydomain.com")
    assert not config.is_origin_allowed("http://localhost:5173")

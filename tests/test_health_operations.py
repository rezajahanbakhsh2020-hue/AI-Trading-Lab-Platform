"""Tests for SystemHealthService liveness, readiness, correlation, and operational diagnostics."""

import pytest
from src.platform.config import PlatformConfig
from src.platform.services.health_operations import SystemHealthService


def test_system_health_liveness():
    service = SystemHealthService()
    is_live, msg = service.check_liveness()
    assert is_live
    assert "Process is live" in msg


def test_system_health_readiness_development():
    service = SystemHealthService()
    is_ready, details = service.check_readiness(active_sessions_count=5)
    assert is_ready
    assert details["active_sessions"] == 5
    assert details["config_valid"] is True


def test_system_health_correlation_id():
    service = SystemHealthService()
    cid1 = service.generate_correlation_id()
    cid2 = service.generate_correlation_id()
    assert cid1.startswith("req_")
    assert cid2.startswith("req_")
    assert cid1 != cid2


def test_operational_diagnostics_sanitized():
    config = PlatformConfig(app_env="development", session_secret="secret_value_1234567890_change_me")
    service = SystemHealthService(config=config)
    diag = service.get_operational_diagnostics(active_sessions_count=2)
    assert diag.liveness is True
    assert diag.readiness is True
    assert diag.system_status == "HEALTHY"
    summary = diag.diagnostics_summary
    assert summary["config"]["session_secret"] == "[REDACTED]"

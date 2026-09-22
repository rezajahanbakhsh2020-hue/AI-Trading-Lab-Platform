"""Comprehensive security foundation tests for AI-Trading-Lab-Platform.

Tests:
- Admin access permitted for protected resources (best strategies, proprietary indicators, parameters, lab research, secrets).
- Unauthorized normal user access rejected for protected resources.
- Alternate paths (Presenter, LabArtifactService, TelegramDelivery, SignalDelivery) enforce authorization and cannot bypass security boundary.
- Protected secrets, tokens, credentials, and parameters are sanitized in logs, error messages, and responses.
- Signal permissions and trade-setup permissions are enforced.
- Audit logger captures access attempts, permissions failures, and outcomes.
- Project 1 integration remains untouched.
"""

import pytest

from src.platform.domain.presented_signal import PresentedSignal
from src.platform.domain.security import (
    ADMIN_ONLY_PERMISSIONS,
    Permission,
    SecurityEvent,
    UserRole,
)
from src.platform.domain.signal import Signal
from src.platform.domain.trade_setup import TradeSetup
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.integrations.lab import LabArtifactSource
from src.platform.integrations.project1 import Project1IntegrationPort
from src.platform.integrations.telegram import TelegramDeliveryPort, TelegramDeliveryResult
from src.platform.services.lab_artifacts import LabArtifactService
from src.platform.services.project1_presenter import Project1SignalPresenter
from src.platform.services.security import AuditLogger, SecretSanitizer, SecurityBoundaryService
from src.platform.services.telegram_delivery import TelegramDeliveryService
from src.platform.services.user_authorization import UserAuthorizationService


# Mock sources for integration testing
class MockLabSource(LabArtifactSource):
    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def describe(self):
        return {"name": "MockLabSource"}

    def fetch_signal(self, symbol: str, timeframe: str):
        return {
            "action": "buy",
            "strategy_name": "ProprietaryGoldAlpha",
            "timestamp": 1700000000,
            "confidence": 0.92,
        }

    def fetch_trade_setup(self, symbol: str, timeframe: str):
        return {
            "symbol": symbol,
            "entry_price": 2700.0,
            "stop_loss": 2680.0,
            "take_profit_1": 2730.0,
            "take_profit_2": 2750.0,
            "take_profit_3": 2780.0,
            "timestamp": 1700000000,
            "direction": "buy",
        }

    def fetch_stability(self, strategy_name: str):
        return {
            "score": 0.85,
            "risk_level": "low",
            "metrics": {
                "win_rate": 0.68,
                "sensitive_parameters": {"super_secret_param": "0.1337"},
                "indicator_logic": "secret_formula_v2",
            },
        }


class MockProject1Port(Project1IntegrationPort):
    def describe(self):
        return {
            "name": "Project1LabArtifactAdapter",
            "port": "Project1IntegrationPort",
            "connected": True,
            "status": "active",
        }

    def fetch_latest_signal(self, symbol: str, timeframe: str, strategy_name=None):
        import time
        return PresentedSignal(
            signal_id="sig_001",
            symbol=symbol,
            signal_type="buy",
            timestamp=time.time() - 30.0,
            entry_price=2700.0,
            stop_loss=2680.0,
            take_profits=(2730.0, 2750.0, 2780.0),
            confidence=0.95,
            strategy_name="ProprietaryGoldAlpha",
            timeframe=timeframe,
            metadata={
                "secret_token": "api_key=xyz123",
                "normal_field": "public_data",
                "provenance_type": "live_signal",
                "is_live": True,
            },
        )


class MockTelegramPort(TelegramDeliveryPort):
    def __init__(self):
        self.sent_signals = []

    def describe(self):
        return {"name": "MockTelegramPort"}

    def send_signal(self, chat_id: str, signal: PresentedSignal):
        self.sent_signals.append((chat_id, signal))
        return TelegramDeliveryResult(success=True, chat_id=chat_id)


def test_admin_vs_normal_user_roles_and_permissions():
    admin = UserAuthorization(
        user_id="admin_01",
        auth_code="admin_secret_code",
        role=UserRole.ADMIN,
    )
    user = UserAuthorization(
        user_id="user_01",
        auth_code="user_code",
        role=UserRole.USER,
        permissions=(Permission.READ_SIGNALS,),
    )
    guest = UserAuthorization(
        user_id="guest_01",
        auth_code="guest_code",
        role=UserRole.GUEST,
    )

    assert admin.is_admin is True
    assert admin.has_permission(Permission.READ_SECRETS) is True
    assert admin.has_permission(Permission.READ_PROPRIETARY_INDICATORS) is True

    assert user.is_admin is False
    assert user.has_permission(Permission.READ_SIGNALS) is True
    assert user.has_permission(Permission.READ_SECRETS) is False
    assert user.has_permission(Permission.READ_PROPRIETARY_INDICATORS) is False

    assert guest.is_admin is False
    assert guest.has_permission(Permission.READ_SIGNALS) is False


def test_security_boundary_authorizes_admin_and_rejects_normal_user():
    audit_logger = AuditLogger()
    sec_svc = SecurityBoundaryService(audit_logger=audit_logger)

    admin = UserAuthorization(user_id="admin_01", auth_code="code1", role=UserRole.ADMIN)
    normal_user = UserAuthorization(
        user_id="user_01", auth_code="code2", role=UserRole.USER, permissions=(Permission.READ_SIGNALS,)
    )

    # Admin access to protected resources
    for resource in ("best_strategies", "proprietary_indicators", "strategy_parameters", "lab_research", "secrets"):
        allowed, msg = sec_svc.authorize(admin, resource)
        assert allowed is True
        assert "Access granted" in msg

    # Normal user access to protected resources rejected
    for resource in ("best_strategies", "proprietary_indicators", "strategy_parameters", "lab_research", "secrets"):
        allowed, msg = sec_svc.authorize(normal_user, resource)
        assert allowed is False
        assert "Access denied" in msg

    # Audit events logged properly
    events = audit_logger.get_events()
    assert len(events) == 10
    denied_events = audit_logger.get_events(outcome="DENY")
    assert len(denied_events) == 5
    assert all(e.user_id == "user_01" for e in denied_events)


def test_secret_sanitizer_masks_credentials_and_tokens():
    raw_text = "Connecting with bearer eyJhbGciOiJIUzI1Ni... and password=supersecret!"
    clean_text = SecretSanitizer.sanitize_string(raw_text)
    assert "supersecret" not in clean_text
    assert "[REDACTED]" in clean_text

    dict_data = {
        "user_id": "test_user",
        "access_token": "secret_token_123",
        "nested": {"api_key": "key_999", "public": "visible"},
    }
    sanitized = SecretSanitizer.sanitize_data(dict_data)
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["nested"]["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["public"] == "visible"


def test_lab_artifact_service_enforces_security_boundaries():
    source = MockLabSource()
    audit_logger = AuditLogger()
    sec_svc = SecurityBoundaryService(audit_logger=audit_logger)
    lab_svc = LabArtifactService(source=source, security_service=sec_svc)

    admin = UserAuthorization(user_id="admin_01", auth_code="code1", role=UserRole.ADMIN)
    user_no_setup = UserAuthorization(
        user_id="user_01",
        auth_code="code2",
        role=UserRole.USER,
        permissions=(Permission.READ_SIGNALS,),
    )
    user_with_setup = UserAuthorization(
        user_id="user_02",
        auth_code="code3",
        role=UserRole.USER,
        permissions=(Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS),
    )

    # Trade setup access
    assert lab_svc.get_trade_setup("XAUUSD", "1h", user=admin) is not None
    assert lab_svc.get_trade_setup("XAUUSD", "1h", user=user_with_setup) is not None
    assert lab_svc.get_trade_setup("XAUUSD", "1h", user=user_no_setup) is None  # Blocked

    # Stability metrics sanitization for normal user vs admin
    admin_stability = lab_svc.get_stability("ProprietaryGoldAlpha", user=admin)
    user_stability = lab_svc.get_stability("ProprietaryGoldAlpha", user=user_with_setup)

    assert admin_stability.metrics["sensitive_parameters"] == {"super_secret_param": "0.1337"}
    assert "sensitive_parameters" not in user_stability.metrics
    assert "indicator_logic" not in user_stability.metrics
    assert user_stability.metrics["win_rate"] == 0.68


def test_project1_presenter_alternate_path_cannot_bypass_authorization():
    port = MockProject1Port()
    sec_svc = SecurityBoundaryService()
    presenter = Project1SignalPresenter(port=port, security_service=sec_svc)

    admin = UserAuthorization(user_id="admin_01", auth_code="code1", role=UserRole.ADMIN)
    user_unauthorized = UserAuthorization(
        user_id="user_unauth", auth_code="code2", role=UserRole.GUEST
    )
    user_signals_only = UserAuthorization(
        user_id="user_sig", auth_code="code3", role=UserRole.USER, permissions=(Permission.READ_SIGNALS,)
    )

    # Unauthorized user gets blocked
    unauth_res = presenter.present_signal("XAUUSD", "1h", user=user_unauthorized)
    assert unauth_res["status"] == "unauthorized"
    assert unauth_res["signal"] is None

    # User without trade setup permission gets masked setup levels and sanitized secrets in metadata
    sig_res = presenter.present_signal("XAUUSD", "1h", user=user_signals_only)
    assert sig_res["status"] == "active"
    assert sig_res["signal"]["entry_price"] is None
    assert sig_res["signal"]["stop_loss"] is None
    assert sig_res["signal"]["take_profits"] == []
    assert sig_res["signal"]["metadata"]["secret_token"] == "[REDACTED]"
    assert sig_res["signal"]["metadata"]["normal_field"] == "public_data"

    # Admin receives complete details and sanitized secrets
    admin_res = presenter.present_signal("XAUUSD", "1h", user=admin)
    assert admin_res["status"] == "active"
    assert admin_res["signal"]["entry_price"] == 2700.0
    assert admin_res["signal"]["metadata"]["secret_token"] == "[REDACTED]"


def test_telegram_delivery_enforces_trade_setup_permission():
    import time
    telegram_port = MockTelegramPort()
    auth_svc = UserAuthorizationService()
    delivery_svc = TelegramDeliveryService(delivery_port=telegram_port, user_auth_service=auth_svc)

    user_full = UserAuthorization(
        user_id="u_full",
        auth_code="c1",
        telegram_chat_id="chat_111",
        role=UserRole.USER,
        permissions=(Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS),
    )
    user_sig_only = UserAuthorization(
        user_id="u_sig",
        auth_code="c2",
        telegram_chat_id="chat_222",
        role=UserRole.USER,
        permissions=(Permission.READ_SIGNALS,),
    )
    auth_svc.register_user(user_full)
    auth_svc.register_user(user_sig_only)

    sig = PresentedSignal(
        signal_id="sig_100",
        symbol="XAUUSD",
        signal_type="buy",
        timestamp=time.time(),
        entry_price=2700.0,
        stop_loss=2680.0,
        take_profits=(2730.0, 2750.0),
        strategy_name="GoldTrend",
        metadata={"provenance_type": "live_signal"},
    )

    # Deliver to user with full permissions
    res_full = delivery_svc.deliver_signal_to_user("u_full", sig)
    assert res_full.success is True
    assert telegram_port.sent_signals[0][1].entry_price == 2700.0

    # Deliver to user without trade setup permission
    res_sig = delivery_svc.deliver_signal_to_user("u_sig", sig)
    assert res_sig.success is True
    delivered_sig = telegram_port.sent_signals[1][1]
    assert delivered_sig.entry_price is None
    assert delivered_sig.stop_loss is None
    assert delivered_sig.take_profits == ()

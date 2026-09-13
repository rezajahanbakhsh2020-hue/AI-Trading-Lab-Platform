"""Focused tests for Part 19 UserAuthorizationService and UserAuthorization."""

import pytest

from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.user_authorization import UserAuthorizationService


def test_user_authorization_policy_and_isolation():
    user = UserAuthorization(
        user_id="usr_01",
        auth_code="secret_code_123",
        telegram_chat_id="chat_999",
        delivery_enabled=True,
        allowed_symbols=("XAUUSD", "EURUSD"),
        allowed_strategies=("Momentum",),
    )

    assert user.can_receive_signal("XAUUSD", "Momentum") is True
    assert user.can_receive_signal("BTCUSD", "Momentum") is False
    assert user.can_receive_signal("XAUUSD", "Breakout") is False


def test_user_authorization_disabled_delivery():
    user = UserAuthorization(
        user_id="usr_02",
        auth_code="code_456",
        telegram_chat_id="chat_888",
        delivery_enabled=False,
    )

    assert user.can_receive_signal("XAUUSD") is False


def test_user_authorization_service_lookup_and_permission():
    svc = UserAuthorizationService()
    user = UserAuthorization(
        user_id="usr_01",
        auth_code="code_123",
        telegram_chat_id="chat_777",
        allowed_symbols=("XAUUSD",),
    )
    svc.register_user(user)

    auth_by_code = svc.authenticate_by_code("code_123")
    assert auth_by_code == user

    ok, reason = svc.evaluate_delivery_permission("usr_01", "XAUUSD")
    assert ok is True
    assert reason == "delivery authorized"

    ok_bad, reason_bad = svc.evaluate_delivery_permission("usr_01", "BTCUSD")
    assert ok_bad is False
    assert "policy does not permit" in reason_bad


def test_user_authorization_to_dict_hides_secrets():
    user = UserAuthorization(
        user_id="usr_01",
        auth_code="SUPER_SECRET_TOKEN",
        telegram_chat_id="chat_123",
    )
    d = user.to_dict()
    assert d["user_id"] == "usr_01"
    assert "auth_code" not in d

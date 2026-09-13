"""Focused tests for Part 19 TelegramDeliveryService and MockTelegramAdapter."""

import pytest

from src.platform.domain.presented_signal import PresentedSignal
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.providers.telegram import MockTelegramAdapter, format_telegram_signal_message
from src.platform.services.telegram_delivery import TelegramDeliveryService
from src.platform.services.user_authorization import UserAuthorizationService


def _signal():
    return PresentedSignal(
        signal_id="sig_999",
        symbol="XAUUSD",
        signal_type="buy",
        timestamp=1000.0,
        entry_price=2000.0,
        stop_loss=1990.0,
        take_profits=(2020.0, 2030.0, 2040.0),
        confidence=0.90,
        strategy_name="Momentum",
        timeframe="1h",
    )


def test_telegram_message_formatting():
    sig = _signal()
    text = format_telegram_signal_message(sig)

    assert "XAUUSD" in text
    assert "BUY" in text
    assert "2000.00" in text
    assert "1990.00" in text
    assert "TP1: 2020.00" in text
    assert "TP2: 2030.00" in text
    assert "TP3: 2040.00" in text
    assert "Confidence: 90.0%" in text


def test_telegram_delivery_success():
    adapter = MockTelegramAdapter(is_configured=True)
    auth_svc = UserAuthorizationService()
    user = UserAuthorization(
        user_id="usr_01",
        auth_code="code_123",
        telegram_chat_id="chat_777",
        delivery_enabled=True,
    )
    auth_svc.register_user(user)

    delivery_svc = TelegramDeliveryService(
        delivery_port=adapter, user_auth_service=auth_svc
    )
    res = delivery_svc.deliver_signal_to_user("usr_01", _signal())

    assert res.success is True
    assert res.chat_id == "chat_777"
    assert len(adapter.delivered_messages) == 1
    assert adapter.delivered_messages[0]["signal_id"] == "sig_999"


def test_telegram_delivery_unauthorized_user():
    adapter = MockTelegramAdapter(is_configured=True)
    auth_svc = UserAuthorizationService()
    delivery_svc = TelegramDeliveryService(
        delivery_port=adapter, user_auth_service=auth_svc
    )

    res = delivery_svc.deliver_signal_to_user("unregistered_user", _signal())

    assert res.success is False
    assert "Authorization denied" in res.reason
    assert len(adapter.delivered_messages) == 0


def test_telegram_unconfigured_credentials_state():
    adapter = MockTelegramAdapter(is_configured=False)
    auth_svc = UserAuthorizationService()
    user = UserAuthorization(
        user_id="usr_01",
        auth_code="code_123",
        telegram_chat_id="chat_777",
    )
    auth_svc.register_user(user)

    delivery_svc = TelegramDeliveryService(
        delivery_port=adapter, user_auth_service=auth_svc
    )
    res = delivery_svc.deliver_signal_to_user("usr_01", _signal())

    assert res.success is False
    assert "not configured" in res.reason

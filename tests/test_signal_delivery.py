"""Focused tests for the signal delivery / notification boundary."""

import pytest

from src.platform.domain.signal import Signal
from src.platform.domain.signal_delivery import (
    DELIVERY_STATUS_DELIVERED,
    DELIVERY_STATUS_NOT_DELIVERED,
    SignalDelivery,
)
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.integrations.signal_delivery import SignalDeliveryPort
from src.platform.providers.signal_delivery import RecordingSignalDeliveryAdapter
from src.platform.services.signal_delivery import (
    REASON_CHANNEL_FAILED,
    REASON_CONSUMER_NOT_AUTHORIZED,
    REASON_DELIVERED,
    REASON_DELIVERY_DISABLED,
    REASON_POLICY_DENIED,
    SignalDeliveryService,
)
from src.platform.services.user_authorization import UserAuthorizationService


def _signal(action="buy", strategy_name="Momentum", timestamp=1000, confidence=0.8):
    return Signal(
        action=action,
        strategy_name=strategy_name,
        timestamp=timestamp,
        confidence=confidence,
    )


def _user(
    user_id="usr_01",
    delivery_enabled=True,
    allowed_symbols=(),
    allowed_strategies=(),
    telegram_chat_id=None,
):
    return UserAuthorization(
        user_id=user_id,
        auth_code="code_" + user_id,
        telegram_chat_id=telegram_chat_id,
        delivery_enabled=delivery_enabled,
        allowed_symbols=allowed_symbols,
        allowed_strategies=allowed_strategies,
    )


def _service(available=True, user=None):
    adapter = RecordingSignalDeliveryAdapter(available=available)
    auth = UserAuthorizationService()
    if user is not None:
        auth.register_user(user)
    return SignalDeliveryService(delivery_port=adapter, user_auth_service=auth), adapter, auth


def test_deliver_generated_signal_to_authorized_consumer():
    user = _user(user_id="usr_01")
    service, adapter, _ = _service(user=user)
    signal = _signal()

    result = service.deliver(consumer_id="usr_01", signal=signal, symbol="XAUUSD")

    assert isinstance(result, SignalDelivery)
    assert result.status == DELIVERY_STATUS_DELIVERED
    assert result.delivered is True
    assert result.reason == REASON_DELIVERED
    assert result.consumer_id == "usr_01"
    assert result.symbol == "XAUUSD"
    assert result.signal is signal
    assert result.signal.action == "buy"
    assert result.channel == "recording"
    assert len(adapter.delivered) == 1
    assert adapter.delivered[0]["strategy_name"] == "Momentum"


def test_unregistered_consumer_is_not_delivered():
    service, adapter, _ = _service()
    result = service.deliver(
        consumer_id="unknown", signal=_signal(), symbol="XAUUSD"
    )

    assert result.status == DELIVERY_STATUS_NOT_DELIVERED
    assert result.delivered is False
    assert result.reason == REASON_CONSUMER_NOT_AUTHORIZED
    assert len(adapter.delivered) == 0


def test_disabled_delivery_is_not_delivered():
    user = _user(user_id="usr_02", delivery_enabled=False)
    service, adapter, _ = _service(user=user)

    result = service.deliver(consumer_id="usr_02", signal=_signal(), symbol="XAUUSD")

    assert result.status == DELIVERY_STATUS_NOT_DELIVERED
    assert result.reason == REASON_DELIVERY_DISABLED
    assert len(adapter.delivered) == 0


def test_symbol_policy_denies_delivery():
    user = _user(user_id="usr_01", allowed_symbols=("XAUUSD",))
    service, adapter, _ = _service(user=user)

    result = service.deliver(consumer_id="usr_01", signal=_signal(), symbol="BTCUSD")

    assert result.status == DELIVERY_STATUS_NOT_DELIVERED
    assert result.reason == REASON_POLICY_DENIED
    assert len(adapter.delivered) == 0


def test_strategy_policy_denies_delivery():
    user = _user(user_id="usr_01", allowed_strategies=("Momentum",))
    service, adapter, _ = _service(user=user)

    result = service.deliver(
        consumer_id="usr_01",
        signal=_signal(strategy_name="Breakout"),
        symbol="XAUUSD",
    )

    assert result.status == DELIVERY_STATUS_NOT_DELIVERED
    assert result.reason == REASON_POLICY_DENIED
    assert len(adapter.delivered) == 0


def test_channel_failure_is_not_delivered():
    user = _user(user_id="usr_01")
    service, adapter, _ = _service(available=False, user=user)

    result = service.deliver(consumer_id="usr_01", signal=_signal(), symbol="XAUUSD")

    assert result.status == DELIVERY_STATUS_NOT_DELIVERED
    assert result.reason == REASON_CHANNEL_FAILED
    assert result.detail == "delivery channel is unavailable"
    assert result.channel == "recording"
    assert len(adapter.delivered) == 0


def test_delivery_result_structure_and_to_dict():
    user = _user(user_id="usr_01")
    service, _, _ = _service(user=user)
    signal = _signal(action="sell", timestamp=42)

    result = service.deliver(consumer_id="usr_01", signal=signal, symbol="XAUUSD")
    payload = result.to_dict()

    assert payload["status"] == DELIVERY_STATUS_DELIVERED
    assert payload["delivered"] is True
    assert payload["consumer_id"] == "usr_01"
    assert payload["symbol"] == "XAUUSD"
    assert payload["signal"]["action"] == "sell"
    assert payload["signal"]["timestamp"] == 42
    assert payload["channel"] == "recording"
    assert "auth_code" not in payload


def test_does_not_require_telegram_destination():
    user = _user(user_id="usr_01", telegram_chat_id=None)
    service, adapter, _ = _service(user=user)

    result = service.deliver(consumer_id="usr_01", signal=_signal(), symbol="XAUUSD")

    assert result.delivered is True
    assert len(adapter.delivered) == 1


def test_hold_and_no_signal_are_still_deliverable():
    user = _user(user_id="usr_01")
    service, adapter, _ = _service(user=user)

    hold = service.deliver(
        consumer_id="usr_01",
        signal=_signal(action="hold", confidence=None),
        symbol="XAUUSD",
    )
    none = service.deliver(
        consumer_id="usr_01",
        signal=_signal(action="no-signal", confidence=None),
        symbol="XAUUSD",
    )

    assert hold.delivered is True
    assert none.delivered is True
    assert hold.signal.action == "hold"
    assert none.signal.action == "no-signal"
    assert len(adapter.delivered) == 2


def test_construction_rejects_invalid_dependencies():
    auth = UserAuthorizationService()
    adapter = RecordingSignalDeliveryAdapter()

    with pytest.raises(ValueError):
        SignalDeliveryService(delivery_port=None, user_auth_service=auth)
    with pytest.raises(ValueError):
        SignalDeliveryService(delivery_port=adapter, user_auth_service=None)
    with pytest.raises(ValueError):
        SignalDeliveryService(delivery_port=object(), user_auth_service=auth)


def test_deliver_rejects_invalid_inputs():
    user = _user()
    service, _, _ = _service(user=user)

    with pytest.raises(ValueError):
        service.deliver(consumer_id="usr_01", signal=object(), symbol="XAUUSD")
    with pytest.raises(ValueError):
        service.deliver(consumer_id="", signal=_signal(), symbol="XAUUSD")
    with pytest.raises(ValueError):
        service.deliver(consumer_id="usr_01", signal=_signal(), symbol="  ")


def test_adapter_implements_port_and_describe():
    adapter = RecordingSignalDeliveryAdapter()
    assert isinstance(adapter, SignalDeliveryPort)
    description = adapter.describe()
    assert description["name"] == "RecordingSignalDeliveryAdapter"
    assert description["available"] is True
    assert description["delivered_count"] == 0


def test_signal_delivery_domain_validation():
    signal = _signal()
    with pytest.raises(ValueError):
        SignalDelivery(
            status="UNKNOWN",
            reason="ok",
            consumer_id="usr_01",
            symbol="XAUUSD",
            signal=signal,
        )
    with pytest.raises(ValueError):
        SignalDelivery(
            status=DELIVERY_STATUS_DELIVERED,
            reason="",
            consumer_id="usr_01",
            symbol="XAUUSD",
            signal=signal,
        )

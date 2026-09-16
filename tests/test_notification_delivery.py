"""Tests for the notification delivery architecture layer.

Verifies domain models, port interfaces, in-memory provider adapter,
NotificationDeliveryService, security/authorization boundaries, secret sanitization,
and AlertService delivery integration.
"""

from dataclasses import FrozenInstanceError
import time
import pytest

from src.platform.domain.alert import AlertRule, MarketAlert
from src.platform.domain.notification_delivery import (
    NOTIFICATION_DELIVERY_DELIVERED,
    NOTIFICATION_DELIVERY_DENIED,
    NOTIFICATION_DELIVERY_FAILED,
    NotificationDelivery,
)
from src.platform.domain.security import UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.integrations.notification_delivery import (
    NotificationDeliveryAttempt,
    NotificationDeliveryPort,
)
from src.platform.providers.notification_delivery import RecordingNotificationDeliveryAdapter
from src.platform.services.alert_service import AlertService
from src.platform.services.notification import NotificationService
from src.platform.services.notification_delivery import (
    REASON_CHANNEL_FAILED,
    REASON_DELIVERY_DISABLED,
    REASON_SECURITY_DENIED,
    REASON_UNREGISTERED_USER,
    NotificationDeliveryService,
)
from src.platform.services.security import SecurityBoundaryService
from src.platform.services.user_authorization import UserAuthorizationService


def _sample_alert(
    alert_id: str = "alt_1",
    kind: str = "price",
    severity: str = "warning",
    message: str = "Price reached 2000.00 with secret api_key=secret_xyz123",
) -> MarketAlert:
    return MarketAlert(
        id=alert_id,
        kind=kind,
        severity=severity,
        status="active",
        message=message,
        symbol="XAUUSD",
        timeframe="1h",
        created_at=time.time(),
        details={"observed_price": 2000.0, "auth_token": "secret_token_abc"},
    )


def _user(
    user_id: str = "usr_01",
    role: UserRole = UserRole.USER,
    delivery_enabled: bool = True,
) -> UserAuthorization:
    return UserAuthorization(
        user_id=user_id,
        auth_code=f"code_{user_id}",
        role=role,
        allowed_symbols=("XAUUSD", "BTCUSD"),
        delivery_enabled=delivery_enabled,
        telegram_chat_id=f"chat_{user_id}",
    )


# ---------------------------------------------------------------------------
# 1. Domain & Port Contract Tests
# ---------------------------------------------------------------------------

def test_notification_delivery_attempt_domain_validation():
    attempt = NotificationDeliveryAttempt(
        success=True,
        user_id="usr_01",
        reason="delivered ok",
        channel="email",
        detail="detail msg",
    )
    assert attempt.success is True
    assert attempt.user_id == "usr_01"
    assert attempt.channel == "email"

    data = attempt.to_dict()
    assert data["success"] is True
    assert data["channel"] == "email"

    with pytest.raises(ValueError):
        NotificationDeliveryAttempt(success="not_a_bool", user_id="u", reason="r")  # type: ignore

    with pytest.raises(ValueError):
        NotificationDeliveryAttempt(success=True, user_id="   ", reason="r")


def test_notification_delivery_domain_validation_and_immutability():
    alert = _sample_alert()
    deliv = NotificationDelivery(
        delivery_id="del_01",
        user_id="usr_01",
        status="DELIVERED",
        reason="delivered ok",
        alert=alert,
        channel="in_memory",
    )
    assert deliv.delivered is True
    assert deliv.user_id == "usr_01"
    assert deliv.alert.id == alert.id

    data = deliv.to_dict()
    assert data["delivered"] is True
    assert data["status"] == NOTIFICATION_DELIVERY_DELIVERED

    with pytest.raises(FrozenInstanceError):
        deliv.status = "FAILED"  # type: ignore

    with pytest.raises(ValueError):
        NotificationDelivery(
            delivery_id="d1",
            user_id="u1",
            status="INVALID_STATUS",
            reason="r",
            alert=alert,
        )


# ---------------------------------------------------------------------------
# 2. Recording Adapter Tests
# ---------------------------------------------------------------------------

def test_recording_adapter_delivers_and_records():
    adapter = RecordingNotificationDeliveryAdapter()
    alert = _sample_alert()

    attempt = adapter.deliver_alert(user_id="usr_01", alert=alert, channel="push")
    assert attempt.success is True
    assert attempt.channel == "push"
    assert len(adapter.delivered) == 1
    assert adapter.delivered[0]["alert"]["id"] == alert.id

    desc = adapter.describe()
    assert desc["name"] == "RecordingNotificationDeliveryAdapter"
    assert desc["recorded_count"] == 1


def test_recording_adapter_channel_enablement_and_unavailability():
    adapter = RecordingNotificationDeliveryAdapter(available=True)
    alert = _sample_alert()

    adapter.set_channel_enabled("email", False)
    attempt_disabled = adapter.deliver_alert(user_id="usr_01", alert=alert, channel="email")
    assert attempt_disabled.success is False
    assert "unavailable" in attempt_disabled.reason

    adapter.available = False
    attempt_unavail = adapter.deliver_alert(user_id="usr_01", alert=alert, channel="in_memory")
    assert attempt_unavail.success is False


def test_recording_adapter_forwards_to_notification_service():
    notif_svc = NotificationService()
    adapter = RecordingNotificationDeliveryAdapter(notification_service=notif_svc)
    alert = _sample_alert()

    attempt = adapter.deliver_alert(user_id="usr_01", alert=alert)
    assert attempt.success is True

    # Check that NotificationService received the inbox notification
    user_auth = _user("usr_01")
    user_notifs = notif_svc.get_notifications(requester=user_auth, target_user_id="usr_01")
    assert len(user_notifs) == 1
    assert "Alert: XAUUSD" in user_notifs[0].title
    assert user_notifs[0].metadata["payload"]["alert_id"] == alert.id


# ---------------------------------------------------------------------------
# 3. NotificationDeliveryService Authorization & Sanitization Tests
# ---------------------------------------------------------------------------

def test_delivery_service_success_path():
    adapter = RecordingNotificationDeliveryAdapter()
    auth_svc = UserAuthorizationService()
    user = _user("usr_01", delivery_enabled=True)
    auth_svc.register_user(user)

    delivery_svc = NotificationDeliveryService(
        delivery_port=adapter,
        user_auth_service=auth_svc,
    )

    alert = _sample_alert()
    res = delivery_svc.deliver_alert_to_user(user_id="usr_01", alert=alert)

    assert res.delivered is True
    assert res.status == NOTIFICATION_DELIVERY_DELIVERED
    assert res.user_id == "usr_01"
    # Verify sanitization stripped secret token from message and details
    assert "secret_xyz123" not in res.alert.message
    assert "[REDACTED]" in res.alert.message
    assert res.alert.details["auth_token"] == "[REDACTED]"


def test_delivery_service_unregistered_user():
    adapter = RecordingNotificationDeliveryAdapter()
    auth_svc = UserAuthorizationService()

    delivery_svc = NotificationDeliveryService(
        delivery_port=adapter,
        user_auth_service=auth_svc,
    )

    alert = _sample_alert()
    res = delivery_svc.deliver_alert_to_user(user_id="unregistered_user", alert=alert)

    assert res.delivered is False
    assert res.status == NOTIFICATION_DELIVERY_DENIED
    assert res.reason == REASON_UNREGISTERED_USER


def test_delivery_service_user_disabled_delivery():
    adapter = RecordingNotificationDeliveryAdapter()
    auth_svc = UserAuthorizationService()
    user = _user("usr_disabled", delivery_enabled=False)
    auth_svc.register_user(user)

    delivery_svc = NotificationDeliveryService(
        delivery_port=adapter,
        user_auth_service=auth_svc,
    )

    alert = _sample_alert()
    res = delivery_svc.deliver_alert_to_user(user_id="usr_disabled", alert=alert)

    assert res.delivered is False
    assert res.status == NOTIFICATION_DELIVERY_DENIED
    assert res.reason == REASON_DELIVERY_DISABLED


def test_delivery_service_channel_failure():
    adapter = RecordingNotificationDeliveryAdapter(available=False)
    auth_svc = UserAuthorizationService()
    user = _user("usr_01")
    auth_svc.register_user(user)

    delivery_svc = NotificationDeliveryService(
        delivery_port=adapter,
        user_auth_service=auth_svc,
    )

    alert = _sample_alert()
    res = delivery_svc.deliver_alert_to_user(user_id="usr_01", alert=alert)

    assert res.delivered is False
    assert res.status == NOTIFICATION_DELIVERY_FAILED
    assert res.reason == REASON_CHANNEL_FAILED


# ---------------------------------------------------------------------------
# 4. AlertService Delivery Integration & Adapter Replacement Tests
# ---------------------------------------------------------------------------

def test_alert_service_deliver_alert_integration():
    adapter = RecordingNotificationDeliveryAdapter()
    auth_svc = UserAuthorizationService()
    auth_svc.register_user(_user("usr_01"))

    deliv_svc = NotificationDeliveryService(
        delivery_port=adapter,
        user_auth_service=auth_svc,
    )

    alert_svc = AlertService(delivery_port=deliv_svc)

    rule = AlertRule(
        rule_id="r1",
        kind="price",
        symbol="XAUUSD",
        condition_type="price_above",
        threshold=1900.0,
    )
    alert = alert_svc.evaluate_rule(rule=rule, current_price=1950.0)
    assert alert is not None

    deliv_res = alert_svc.deliver_alert(alert=alert, user_id="usr_01")
    assert deliv_res is not None
    assert deliv_res.delivered is True
    assert deliv_res.user_id == "usr_01"


class CustomMockDeliveryAdapter(NotificationDeliveryPort):
    """Custom replaceable adapter for testing contract swap."""

    def __init__(self) -> None:
        self.last_delivered_user: str = ""

    def deliver_alert(
        self, user_id: str, alert: MarketAlert, channel: str | None = None
    ) -> NotificationDeliveryAttempt:
        self.last_delivered_user = user_id
        return NotificationDeliveryAttempt(
            success=True,
            user_id=user_id,
            reason="custom adapter delivery ok",
            channel="custom",
        )

    def describe(self) -> dict[str, any]:
        return {"name": "CustomMockDeliveryAdapter"}


def test_adapter_replacement_contract():
    custom_adapter = CustomMockDeliveryAdapter()
    delivery_svc = NotificationDeliveryService(delivery_port=custom_adapter)

    alert = _sample_alert()
    res = delivery_svc.deliver_alert_to_user(
        user_id="usr_custom",
        alert=alert,
        requester=_user("usr_custom"),
    )

    assert res.delivered is True
    assert custom_adapter.last_delivered_user == "usr_custom"
    assert res.channel == "custom"

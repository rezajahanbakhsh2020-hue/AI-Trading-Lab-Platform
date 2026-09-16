"""Tests for the notification delivery architecture layer (PR #33 correction).

Verifies NotificationDeliveryPort, RecordingNotificationDeliveryAdapter,
NotificationDeliveryService, strict user isolation, secret sanitization, honest
in-process delivery semantics, adapter contract swapping, and AlertService integration.
"""

from dataclasses import FrozenInstanceError
import time
import pytest

from src.platform.domain.alert import AlertRule, MarketAlert
from src.platform.domain.notification import (
    NotificationCategory,
    NotificationEvent,
    NotificationSeverity,
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
    REASON_DELIVERY_DISABLED,
    REASON_UNREGISTERED_USER,
    NotificationDeliveryService,
)
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


def _sample_event(
    event_id: str = "evt_1",
    target_user_id: str = "usr_01",
) -> NotificationEvent:
    return NotificationEvent(
        event_id=event_id,
        event_type="SIGNAL_EMITTED",
        category=NotificationCategory.SIGNAL,
        severity=NotificationSeverity.INFO,
        title="New Signal Emitted",
        message="BUY signal for XAUUSD with secret api_key=secret_xyz123",
        timestamp=time.time(),
        target_user_id=target_user_id,
        payload={"secret_key": "my_secret_key"},
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
# 1. Port Contract & Infrastructure Model Tests
# ---------------------------------------------------------------------------

def test_notification_delivery_attempt_contract():
    attempt = NotificationDeliveryAttempt(
        success=True,
        user_id="usr_01",
        reason="recorded in-process",
        channel="in_process",
        detail="detail msg",
    )
    assert attempt.success is True
    assert attempt.user_id == "usr_01"
    assert attempt.channel == "in_process"

    data = attempt.to_dict()
    assert data["success"] is True
    assert data["channel"] == "in_process"

    with pytest.raises(ValueError):
        NotificationDeliveryAttempt(success="not_a_bool", user_id="u", reason="r")  # type: ignore

    with pytest.raises(ValueError):
        NotificationDeliveryAttempt(success=True, user_id="   ", reason="r")


# ---------------------------------------------------------------------------
# 2. Honest In-Process Recording Adapter Tests
# ---------------------------------------------------------------------------

def test_recording_adapter_delivers_alert_and_event_with_honest_semantics():
    adapter = RecordingNotificationDeliveryAdapter()
    alert = _sample_alert()
    event = _sample_event()

    att_alert = adapter.deliver_alert(user_id="usr_01", alert=alert)
    assert att_alert.success is True
    assert att_alert.channel == "in_process"
    assert "recorded in-process" in att_alert.reason

    att_event = adapter.deliver_event(user_id="usr_01", event=event)
    assert att_event.success is True
    assert att_event.channel == "in_process"

    assert len(adapter.attempts) == 2
    assert adapter.describe()["recorded_count"] == 2


def test_recording_adapter_forwards_to_existing_notification_service():
    notif_svc = NotificationService()
    adapter = RecordingNotificationDeliveryAdapter(notification_service=notif_svc)
    alert = _sample_alert()

    att = adapter.deliver_alert(user_id="usr_01", alert=alert)
    assert att.success is True

    # Confirm inbox received notification using existing Notification domain model
    user_auth = _user("usr_01")
    notifs = notif_svc.get_notifications(requester=user_auth, target_user_id="usr_01")
    assert len(notifs) == 1
    assert notifs[0].category == NotificationCategory.MARKET_HEALTH
    assert "Alert: XAUUSD" in notifs[0].title


# ---------------------------------------------------------------------------
# 3. NotificationDeliveryService User Isolation & Authorization Tests
# ---------------------------------------------------------------------------

def test_user_isolation_rejects_unauthorized_cross_user_delivery():
    adapter = RecordingNotificationDeliveryAdapter()
    auth_svc = UserAuthorizationService()
    user1 = _user("usr_01", role=UserRole.USER)
    user2 = _user("usr_02", role=UserRole.USER)
    auth_svc.register_user(user1)
    auth_svc.register_user(user2)

    delivery_svc = NotificationDeliveryService(
        delivery_port=adapter,
        user_auth_service=auth_svc,
    )

    alert = _sample_alert()
    # User 1 attempts to deliver alert to User 2's user_id -> MUST raise PermissionError
    with pytest.raises(PermissionError) as exc_info:
        delivery_svc.deliver_alert_to_user(
            target_user_id="usr_02",
            alert=alert,
            requester=user1,
        )
    assert "not authorized to deliver notifications for user 'usr_02'" in str(exc_info.value)


def test_admin_allowed_cross_user_delivery():
    adapter = RecordingNotificationDeliveryAdapter()
    auth_svc = UserAuthorizationService()
    admin_user = _user("admin_user", role=UserRole.ADMIN)
    target_user = _user("target_user", role=UserRole.USER)
    auth_svc.register_user(admin_user)
    auth_svc.register_user(target_user)

    delivery_svc = NotificationDeliveryService(
        delivery_port=adapter,
        user_auth_service=auth_svc,
    )

    alert = _sample_alert()
    res = delivery_svc.deliver_alert_to_user(
        target_user_id="target_user",
        alert=alert,
        requester=admin_user,
    )
    assert res.success is True
    assert res.user_id == "target_user"


def test_delivery_service_sanitizes_secrets():
    adapter = RecordingNotificationDeliveryAdapter()
    auth_svc = UserAuthorizationService()
    user = _user("usr_01")
    auth_svc.register_user(user)

    delivery_svc = NotificationDeliveryService(
        delivery_port=adapter,
        user_auth_service=auth_svc,
    )

    alert = _sample_alert(message="Token token=secret_xyz123 exposed")
    att = delivery_svc.deliver_alert_to_user(
        target_user_id="usr_01",
        alert=alert,
        requester=user,
    )
    assert att.success is True
    recorded_alert = adapter.attempts[0]["alert"]
    assert "secret_xyz123" not in recorded_alert["message"]
    assert "[REDACTED]" in recorded_alert["message"]


def test_delivery_service_disabled_user_rejected():
    adapter = RecordingNotificationDeliveryAdapter()
    auth_svc = UserAuthorizationService()
    user_disabled = _user("usr_disabled", delivery_enabled=False)
    auth_svc.register_user(user_disabled)

    delivery_svc = NotificationDeliveryService(
        delivery_port=adapter,
        user_auth_service=auth_svc,
    )

    alert = _sample_alert()
    att = delivery_svc.deliver_alert_to_user(
        target_user_id="usr_disabled",
        alert=alert,
        requester=user_disabled,
    )
    assert att.success is False
    assert att.reason == REASON_DELIVERY_DISABLED


# ---------------------------------------------------------------------------
# 4. AlertService Integration & Replaceable Adapter Test Doubles
# ---------------------------------------------------------------------------

def test_alert_service_delivers_via_abstract_port():
    adapter = RecordingNotificationDeliveryAdapter()
    alert_svc = AlertService(delivery_port=adapter)

    rule = AlertRule(
        rule_id="r1",
        kind="price",
        symbol="XAUUSD",
        condition_type="price_above",
        threshold=1900.0,
    )
    alert = alert_svc.evaluate_rule(rule=rule, current_price=1950.0)
    assert alert is not None

    att = alert_svc.deliver_alert(alert=alert, user_id="usr_01")
    assert att is not None
    assert att.success is True
    assert att.user_id == "usr_01"


class MockReplaceableDeliveryAdapter(NotificationDeliveryPort):
    """Custom replaceable adapter for testing Port double substitution."""

    def __init__(self) -> None:
        self.delivered_targets: list[str] = []

    def deliver_event(
        self, user_id: str, event: NotificationEvent, channel: str | None = None
    ) -> NotificationDeliveryAttempt:
        self.delivered_targets.append(user_id)
        return NotificationDeliveryAttempt(
            success=True,
            user_id=user_id,
            reason="delivered event via replaceable adapter",
            channel="custom_adapter",
        )

    def deliver_alert(
        self, user_id: str, alert: MarketAlert, channel: str | None = None
    ) -> NotificationDeliveryAttempt:
        self.delivered_targets.append(user_id)
        return NotificationDeliveryAttempt(
            success=True,
            user_id=user_id,
            reason="delivered alert via replaceable adapter",
            channel="custom_adapter",
        )

    def describe(self) -> dict[str, any]:
        return {"name": "MockReplaceableDeliveryAdapter"}


def test_replaceable_adapter_double():
    mock_adapter = MockReplaceableDeliveryAdapter()
    delivery_svc = NotificationDeliveryService(delivery_port=mock_adapter)

    alert = _sample_alert()
    att = delivery_svc.deliver_alert_to_user(
        target_user_id="usr_replaceable",
        alert=alert,
        requester=_user("usr_replaceable"),
    )
    assert att.success is True
    assert att.channel == "custom_adapter"
    assert "usr_replaceable" in mock_adapter.delivered_targets

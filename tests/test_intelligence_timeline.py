"""Tests for Unified Intelligence Timeline and Explainability Boundary Services."""

import time
import pytest

from src.platform.domain.security import Permission, UserRole
from src.platform.domain.timeline import (
    ExplainabilityPayload,
    TimelineCategory,
    TimelineItem,
    TimelineSeverity,
)
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.intelligence_timeline import (
    ExplainabilityService,
    IntelligenceTimelineService,
)
from src.platform.services.security import SecurityBoundaryService


@pytest.fixture
def mock_snapshot():
    return {
        "project1": {
            "connected": True,
            "port": "Project1IntegrationPort",
            "adapterName": "Project1LabArtifactAdapter",
            "message": "Connected",
        },
        "market": {
            "symbol": "XAUUSD",
            "timeframe": "1h",
            "status": "connected",
            "message": "Streaming market data",
            "lastFetchedAt": "Mon, 15 Sep 2026 10:00:00 GMT",
            "provider": {"name": "BiQuoteProvider"},
            "quote": {"bid": 2650.0, "ask": 2650.5},
        },
        "signal": {
            "signalId": "sig_xauusd_1001",
            "action": "BUY",
            "timestamp": "Mon, 15 Sep 2026 10:00:00 GMT",
            "confidence": 0.88,
            "strategyName": "GoldTrendv1",
            "timeframe": "1h",
            "status": "active",
            "metadata": {
                "source": "Project1",
                "indicator_logic": "SECRET_SMA_CROSSOVER_LOGIC",
                "sensitive_parameters": {"fast_len": 12, "slow_len": 26},
            },
        },
        "risk": {
            "entry": 2650.5,
            "stopLoss": 2635.0,
            "takeProfits": [2670.0, 2690.0],
            "status": "available",
        },
        "monitoring": {
            "freshness": "fresh",
            "health": "healthy",
            "message": "System operational",
        },
        "providers": {
            "message": "All providers connected",
        },
    }


@pytest.fixture
def standard_user():
    return UserAuthorization(
        user_id="user_123",
        auth_code="code_123",
        role=UserRole.USER,
        permissions=(Permission.READ_SIGNALS, Permission.READ_TRADE_SETUPS),
    )


@pytest.fixture
def admin_user():
    return UserAuthorization(
        user_id="admin_999",
        auth_code="code_999",
        role=UserRole.ADMIN,
        permissions=(Permission.ADMIN_ALL,),
    )


def test_timeline_item_creation():
    item = TimelineItem(
        item_id="item-1",
        timestamp=1000.0,
        category=TimelineCategory.SIGNAL,
        severity=TimelineSeverity.SUCCESS,
        title="Test Signal",
        summary="Summary of signal",
        source="TestPort",
        route="/signals",
        explainable=True,
        payload={"key": "val"},
    )
    assert item.item_id == "item-1"
    assert item.category == TimelineCategory.SIGNAL
    assert item.to_dict()["explainable"] is True


def test_timeline_building_chronological_ordering(mock_snapshot, standard_user):
    service = IntelligenceTimelineService()

    notifications = [
        {
            "notification_id": "notif-1",
            "user_id": "user_123",
            "category": "system",
            "severity": "info",
            "title": "System Update",
            "message": "Maintenance complete",
            "timestamp": 1700000100.0,
        }
    ]

    workspace_events = [
        {
            "event_id": "ws-1",
            "user_id": "user_123",
            "title": "Watchlist Created",
            "summary": "Added Crypto watchlist",
            "timestamp": 1700000200.0,
        }
    ]

    items = service.build_timeline(
        user=standard_user,
        snapshot=mock_snapshot,
        notifications=notifications,
        workspace_events=workspace_events,
    )

    assert len(items) >= 4
    # Check chronological descending order (newest timestamp first)
    for i in range(len(items) - 1):
        assert items[i].timestamp >= items[i + 1].timestamp


def test_user_isolation_in_timeline(mock_snapshot, standard_user):
    service = IntelligenceTimelineService()

    notifications = [
        {
            "notification_id": "notif-user-123",
            "user_id": "user_123",
            "category": "system",
            "severity": "info",
            "title": "Your Alert",
            "message": "User 123 alert",
            "timestamp": 1700000000.0,
        },
        {
            "notification_id": "notif-user-456",
            "user_id": "user_456",
            "category": "system",
            "severity": "info",
            "title": "Other Alert",
            "message": "User 456 alert",
            "timestamp": 1700000000.0,
        },
    ]

    items = service.build_timeline(
        user=standard_user,
        snapshot=mock_snapshot,
        notifications=notifications,
    )

    notif_titles = [it.title for it in items if it.source == "NotificationService"]
    assert "Your Alert" in notif_titles
    assert "Other Alert" not in notif_titles


def test_protected_data_filtering_for_standard_user(mock_snapshot, standard_user):
    service = IntelligenceTimelineService()

    items = service.build_timeline(
        user=standard_user,
        snapshot=mock_snapshot,
    )

    sig_item = next(it for it in items if it.category == TimelineCategory.SIGNAL)
    meta = sig_item.payload.get("metadata", {})

    # Sensitive parameters and indicator logic must be redacted/stripped for standard user
    assert "indicator_logic" not in meta
    assert "sensitive_parameters" not in meta
    assert meta.get("source") == "Project1"


def test_explainability_boundary(mock_snapshot, standard_user, admin_user):
    service = IntelligenceTimelineService()
    explain_service = ExplainabilityService()

    items = service.build_timeline(
        user=standard_user,
        snapshot=mock_snapshot,
    )

    sig_item = next(it for it in items if it.category == TimelineCategory.SIGNAL)

    explain_payload = explain_service.generate_explainability(
        user=standard_user,
        item=sig_item,
        snapshot=mock_snapshot,
    )

    assert isinstance(explain_payload, ExplainabilityPayload)
    assert explain_payload.item_id == sig_item.item_id
    assert explain_payload.source == "Project1IntegrationPort"
    assert explain_payload.permitted_market_context["symbol"] == "XAUUSD"
    assert explain_payload.permitted_risk_context["entry_level"] == 2650.5

    # Check secret redaction in explainability metadata
    assert "indicator_logic" not in explain_payload.permitted_metadata
    assert "sensitive_parameters" not in explain_payload.permitted_metadata


def test_unauthorized_explainability_access(mock_snapshot):
    explain_service = ExplainabilityService()

    # User with no READ_SIGNALS permission
    guest_user = UserAuthorization(
        user_id="guest_1",
        auth_code="code_guest",
        role=UserRole.GUEST,
        permissions=(),
    )

    sig_item = TimelineItem(
        item_id="sig-item-1",
        timestamp=time.time(),
        category=TimelineCategory.SIGNAL,
        severity=TimelineSeverity.SUCCESS,
        title="Signal Title",
        summary="Signal summary",
        source="Project1IntegrationPort",
        route="/signals",
        explainable=True,
    )

    with pytest.raises(PermissionError):
        explain_service.generate_explainability(
            user=guest_user,
            item=sig_item,
            snapshot=mock_snapshot,
        )

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
            "symbol": "XAUUSD",
            "action": "BUY",
            "timestamp": time.time() - 50.0,
            "confidence": 0.88,
            "strategyName": "GoldTrendv1",
            "timeframe": "1h",
            "status": "active",
            "metadata": {
                "source": "Project1",
                "provenance_type": "live_signal",
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


def test_historical_2023_artifact_produces_zero_signal_timeline_events(admin_user):
    """Prove p1_xauusd_1h_1700000000 (Nov 2023) produces ZERO SIGNAL timeline events."""
    service = IntelligenceTimelineService()

    historical_snapshot = {
        "project1": {"connected": True, "port": "Project1IntegrationPort", "adapterName": "Project1GatewayAdapter"},
        "market": {"symbol": "XAUUSD", "timeframe": "1h", "status": "connected"},
        "signal": {
            "signalId": "p1_xauusd_1h_1700000000",
            "symbol": "XAUUSD",
            "action": "BUY",
            "timestamp": 1700000000.0,  # Nov 14, 2023
            "confidence": 0.88,
            "strategyName": "GoldTrendv1",
            "timeframe": "1h",
            "status": "active",
            "metadata": {"provenance_type": "lab_artifact", "is_historical": True},
        },
    }

    items = service.build_timeline(user=admin_user, snapshot=historical_snapshot)
    sig_items = [it for it in items if it.category == TimelineCategory.SIGNAL]
    assert len(sig_items) == 0


def test_missing_provenance_or_invalid_status_produces_zero_signal_timeline_events(admin_user):
    """Prove missing provenance, stale status, symbol mismatch, or future ts produce ZERO SIGNAL timeline events."""
    service = IntelligenceTimelineService()

    # 1. Missing provenance
    snap_no_prov = {
        "project1": {"connected": True},
        "market": {"symbol": "XAUUSD"},
        "signal": {
            "signalId": "sig_live_1",
            "symbol": "XAUUSD",
            "action": "BUY",
            "timestamp": time.time() - 10,
            "status": "active",
            "metadata": {},
        },
    }
    assert len([it for it in service.build_timeline(user=admin_user, snapshot=snap_no_prov) if it.category == TimelineCategory.SIGNAL]) == 0

    # 2. Stale / no-signal status
    snap_stale = {
        "project1": {"connected": True},
        "market": {"symbol": "XAUUSD"},
        "signal": {
            "signalId": "sig_live_2",
            "symbol": "XAUUSD",
            "action": "BUY",
            "timestamp": time.time() - 10,
            "status": "stale",
            "metadata": {"provenance_type": "live_signal"},
        },
    }
    assert len([it for it in service.build_timeline(user=admin_user, snapshot=snap_stale) if it.category == TimelineCategory.SIGNAL]) == 0

    # 3. Symbol mismatch (signal for EURUSD, market requested XAUUSD)
    snap_mismatch = {
        "project1": {"connected": True},
        "market": {"symbol": "XAUUSD"},
        "signal": {
            "signalId": "sig_live_3",
            "symbol": "EURUSD",
            "action": "BUY",
            "timestamp": time.time() - 10,
            "status": "active",
            "metadata": {"provenance_type": "live_signal"},
        },
    }
    assert len([it for it in service.build_timeline(user=admin_user, snapshot=snap_mismatch) if it.category == TimelineCategory.SIGNAL]) == 0

    # 4. Future timestamp
    snap_future = {
        "project1": {"connected": True},
        "market": {"symbol": "XAUUSD"},
        "signal": {
            "signalId": "sig_live_4",
            "symbol": "XAUUSD",
            "action": "BUY",
            "timestamp": time.time() + 1000,
            "status": "active",
            "metadata": {"provenance_type": "live_signal"},
        },
    }
    assert len([it for it in service.build_timeline(user=admin_user, snapshot=snap_future) if it.category == TimelineCategory.SIGNAL]) == 0


def test_valid_current_live_signal_produces_exactly_one_signal_timeline_event(admin_user):
    """Prove genuinely valid current live signal produces exactly 1 SIGNAL timeline event with true timestamp."""
    service = IntelligenceTimelineService()
    now_ts = time.time() - 20.0

    valid_snap = {
        "project1": {"connected": True, "port": "Project1IntegrationPort", "adapterName": "Project1GatewayAdapter"},
        "market": {"symbol": "XAUUSD", "timeframe": "1h", "status": "connected"},
        "signal": {
            "signalId": "p1_xauusd_1h_live_valid",
            "symbol": "XAUUSD",
            "action": "BUY",
            "timestamp": now_ts,
            "confidence": 0.92,
            "strategyName": "GoldTrendv1",
            "timeframe": "1h",
            "status": "active",
            "metadata": {"provenance_type": "live_signal", "is_live": True},
        },
    }

    items = service.build_timeline(user=admin_user, snapshot=valid_snap)
    sig_items = [it for it in items if it.category == TimelineCategory.SIGNAL]

    assert len(sig_items) == 1
    item = sig_items[0]
    assert item.item_id == "timeline-sig-p1_xauusd_1h_live_valid"
    assert item.timestamp == pytest.approx(now_ts, abs=0.01)
    assert item.payload["signal_id"] == "p1_xauusd_1h_live_valid"
    assert item.payload["symbol"] == "XAUUSD"

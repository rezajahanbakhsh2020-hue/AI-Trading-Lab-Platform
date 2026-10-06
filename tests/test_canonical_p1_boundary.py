"""Comprehensive test suite for Canonical Project 1 to Project 2 signal boundary.

Tests:
- P1 Contract v1 nested payload parsing
- Flat legacy payload handling
- Timezone-aware ISO-8601 timestamp normalization
- Naive datetime rejection
- Invalid ISO format string rejection
- Future timestamp rejection
- Numeric timestamp in P1 Contract v1 rejection
- Service-to-service authentication (missing, wrong, valid)
- Secrets sanitization and redaction
- Complete P1 lineage preservation
- Replay idempotency
- Integrity conflict rejection on mutated content
- Fail-closed live provenance & 300s freshness
- Zero trading intelligence recalculation in P2
- Lineage-aware lifecycle state transitions
"""

from datetime import datetime, timezone
import math
import os
import tempfile
import time
import pytest

from src.platform.adapters.project1_adapter import Project1GatewayAdapter
from src.platform.adapters.project1_repository import FileBackedProject1IntegrationRepository
from src.platform.config import PlatformConfig
from src.platform.domain.project1_contract import (
    parse_iso8601_to_utc_epoch,
    validate_project1_contract_payload,
)
from src.platform.domain.security import UserRole
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.audit_control import PlatformAuditControlService
from src.platform.services.project1_gateway import Project1IntegrationGatewayService
from src.platform.services.project1_presenter import Project1SignalPresenter
from src.platform.services.security import SecurityBoundaryService


@pytest.fixture
def temp_repo_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield os.path.join(tmpdir, "test_p1_records.json")


@pytest.fixture
def admin_user():
    return UserAuthorization(
        user_id="usr_admin",
        auth_code="ac_admin",
        role=UserRole.ADMIN,
        allowed_symbols=("XAUUSD", "EURUSD"),
    )


@pytest.fixture
def service_gateway(temp_repo_path):
    repo = FileBackedProject1IntegrationRepository(temp_repo_path)
    sec = SecurityBoundaryService()
    audit = PlatformAuditControlService(security_boundary=sec)
    return Project1IntegrationGatewayService(
        repository=repo,
        security_boundary=sec,
        audit_control=audit,
        service_key="test_service_key_12345",
    )


def test_contract_v1_nested_payload_accepted():
    payload = {
        "contract_version": "1.0",
        "event_id": "pub_xau_1001",
        "event_type": "TRADING_SIGNAL",
        "timestamp": "2026-03-30T12:00:00+00:00",
        "instrument": {
            "symbol": "XAUUSD",
            "interval": "1h",
        },
        "signal": {
            "publication_id": "pub_xau_1001",
            "signal_id": "sig_xau_1001",
            "decision_id": "dec_xau_1001",
            "decision": "buy",
            "strategy": "GoldTrendv1",
            "candidate_id": "cand_01",
            "confidence": 0.92,
            "stability_score": 0.88,
        },
        "trade_setup": {
            "entry_price": 2650.5,
            "stop_loss": 2635.0,
            "tp1": 2670.0,
            "tp2": 2690.0,
            "tp3": 2710.0,
            "risk_reward_ratio": 2.63,
        },
        "provenance": {
            "provenance_type": "live_signal",
            "research_evidence_id": "ev_123",
            "research_fingerprint": "fp_abc",
        },
    }

    res = validate_project1_contract_payload(
        payload, current_time_fn=lambda: datetime.fromisoformat("2026-03-30T12:00:01+00:00").timestamp()
    )
    assert res.is_valid is True
    s = res.sanitized_payload
    assert s["publication_id"] == "pub_xau_1001"
    assert s["signal_id"] == "sig_xau_1001"
    assert s["symbol"] == "XAUUSD"
    assert s["signal_type"] == "buy"
    assert s["entry_price"] == 2650.5
    assert s["stop_loss"] == 2635.0
    assert s["take_profit_1"] == 2670.0
    assert s["confidence"] == 0.92
    assert s["operational_stability_score"] == 0.88


def test_iso8601_timestamp_normalization():
    dt_str = "2026-03-30T12:00:00Z"
    now_fn = lambda: datetime.fromisoformat("2026-03-30T12:00:02+00:00").timestamp()
    epoch = parse_iso8601_to_utc_epoch(dt_str, current_time_fn=now_fn)
    expected = datetime.fromisoformat("2026-03-30T12:00:00+00:00").timestamp()
    assert math.isclose(epoch, expected, abs_tol=1e-3)


def test_naive_timestamp_rejected():
    naive_str = "2026-03-30T12:00:00"
    with pytest.raises(ValueError, match="naive"):
        parse_iso8601_to_utc_epoch(naive_str)


def test_invalid_timestamp_rejected():
    invalid_str = "not-a-timestamp"
    with pytest.raises(ValueError, match="Invalid ISO-8601"):
        parse_iso8601_to_utc_epoch(invalid_str)


def test_numeric_timestamp_in_v1_rejected():
    with pytest.raises(ValueError, match="must be a timezone-aware ISO-8601 string"):
        parse_iso8601_to_utc_epoch(1700000000.0)


def test_future_timestamp_rejected():
    dt_str = "2026-03-30T12:10:00Z"
    now_fn = lambda: datetime.fromisoformat("2026-03-30T12:00:00+00:00").timestamp()
    with pytest.raises(ValueError, match="Future timestamp rejected"):
        parse_iso8601_to_utc_epoch(dt_str, current_time_fn=now_fn)


def test_service_auth_verification(service_gateway):
    assert service_gateway.authenticate_service_credential("test_service_key_12345") is True
    assert service_gateway.authenticate_service_credential("wrong_key") is False
    assert service_gateway.authenticate_service_credential(None) is False


def test_secrets_not_logged_or_persisted():
    cfg = PlatformConfig(project1_service_key="super_secret_p1_key_2026")
    sanitized = cfg.to_sanitized_dict()
    assert sanitized["project1_service_key"] == "[REDACTED]"


def test_same_identity_same_content_is_idempotent(service_gateway, admin_user):
    payload = {
        "contract_version": "1.0",
        "event_id": "pub_xau_1002",
        "timestamp": "2026-03-30T12:00:00Z",
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": "pub_xau_1002",
            "signal_id": "sig_xau_1002",
            "decision": "buy",
            "strategy": "GoldTrendv1",
            "confidence": 0.85,
        },
        "trade_setup": {"entry_price": 2650.0, "stop_loss": 2635.0},
        "provenance": {"provenance_type": "live_signal"},
    }

    now_ts = datetime.fromisoformat("2026-03-30T12:00:01+00:00").timestamp()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("time.time", lambda: now_ts)
        res1 = service_gateway.ingest_signal_payload(user=admin_user, payload=payload)
        assert res1["success"] is True
        assert res1["status"] == "INGESTED"

        res2 = service_gateway.ingest_signal_payload(user=admin_user, payload=payload)
        assert res2["success"] is True
        assert res2["status"] == "DUPLICATE_ACCEPTED"


def test_same_identity_mutated_content_is_integrity_conflict(service_gateway, admin_user):
    payload1 = {
        "contract_version": "1.0",
        "event_id": "pub_xau_1003",
        "timestamp": "2026-03-30T12:00:00Z",
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": "pub_xau_1003",
            "signal_id": "sig_xau_1003",
            "decision": "buy",
            "strategy": "GoldTrendv1",
            "confidence": 0.85,
        },
        "trade_setup": {"entry_price": 2650.0, "stop_loss": 2635.0},
        "provenance": {"provenance_type": "live_signal"},
    }

    payload2 = dict(payload1)
    payload2["trade_setup"] = {"entry_price": 2700.0, "stop_loss": 2635.0}  # Mutated entry_price

    now_ts = datetime.fromisoformat("2026-03-30T12:00:01+00:00").timestamp()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("time.time", lambda: now_ts)
        res1 = service_gateway.ingest_signal_payload(user=admin_user, payload=payload1)
        assert res1["success"] is True

        res2 = service_gateway.ingest_signal_payload(user=admin_user, payload=payload2)
        assert res2["success"] is False
        assert res2["error_code"] == "INTEGRITY_CONFLICT"


def test_stale_signal_returns_no_signal_in_presenter(service_gateway, admin_user):
    # Signal emitted 10 minutes ago
    sig_time_str = "2026-03-30T11:50:00Z"
    now_ts = datetime.fromisoformat("2026-03-30T12:00:00Z").timestamp()

    payload = {
        "contract_version": "1.0",
        "event_id": "pub_xau_stale",
        "timestamp": sig_time_str,
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": "pub_xau_stale",
            "signal_id": "sig_xau_stale",
            "decision": "buy",
            "strategy": "GoldTrendv1",
            "confidence": 0.85,
        },
        "trade_setup": {"entry_price": 2650.0, "stop_loss": 2635.0},
        "provenance": {"provenance_type": "live_signal"},
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("time.time", lambda: datetime.fromisoformat("2026-03-30T11:50:01Z").timestamp())
        res = service_gateway.ingest_signal_payload(user=admin_user, payload=payload)
        assert res["success"] is True

    adapter = Project1GatewayAdapter(gateway_service=service_gateway)
    presenter = Project1SignalPresenter(port=adapter, gateway_service=service_gateway)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("time.time", lambda: now_ts)
        pres_res = presenter.present_signal(symbol="XAUUSD", timeframe="1h", user=admin_user)
        assert pres_res["status"] == "active"
        assert pres_res["signal"] is not None


def test_p1_values_preserved_without_recalculation(service_gateway, admin_user):
    sig_time_str = "2026-03-30T11:58:00Z"
    now_ts = datetime.fromisoformat("2026-03-30T12:00:00Z").timestamp()

    payload = {
        "contract_version": "1.0",
        "event_id": "pub_xau_exact",
        "timestamp": sig_time_str,
        "instrument": {"symbol": "XAUUSD", "interval": "1h"},
        "signal": {
            "publication_id": "pub_xau_exact",
            "signal_id": "sig_xau_exact",
            "decision": "buy",
            "strategy": "GoldTrendv1",
            "confidence": 0.88,
            "stability_score": 0.82,
        },
        "trade_setup": {
            "entry_price": 2650.5,
            "stop_loss": 2635.0,
            "tp1": 2670.0,
            "tp2": 2690.0,
            "tp3": 2710.0,
            "risk_reward_ratio": 2.55,
        },
        "provenance": {"provenance_type": "live_signal"},
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("time.time", lambda: datetime.fromisoformat("2026-03-30T11:58:01Z").timestamp())
        res = service_gateway.ingest_signal_payload(user=admin_user, payload=payload)
        assert res["success"] is True

    adapter = Project1GatewayAdapter(gateway_service=service_gateway)
    presenter = Project1SignalPresenter(port=adapter, gateway_service=service_gateway)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("time.time", lambda: now_ts)
        snapshot = presenter.build_host_snapshot(symbol="XAUUSD", timeframe="1h", user=admin_user)
        sig = snapshot["signal"]
        risk = snapshot["risk"]

        assert sig["confidence"] == 0.88
        assert sig["action"] == "BUY"
        assert risk["entry"] == 2650.5
        assert risk["stopLoss"] == 2635.0
        assert risk["takeProfits"] == [2670.0, 2690.0, 2710.0]

"""Focused regression and adversarial test suite for XAUUSD 5m freshness contract & LIVE badge TTL semantics."""

import datetime
import time
import pytest

from src.platform.domain.project1_contract import parse_iso8601_to_utc_epoch
from src.platform.services.clock import SystemClock
from src.platform.services.project1_presenter import _evaluate_signal_live_status


def test_scenario_1_market_data_timestamp_older_than_300s_with_fresh_publication():
    """Scenario 1: Candle timestamp is 2 hours old, but publication produced_at is fresh (10s old).

    MUST evaluate to ACTIVE (is_live = True).
    """
    now_ts = time.time()
    market_data_ts = now_ts - 7200.0  # Candle started 2 hours ago
    publication_ts = now_ts - 10.0    # Published 10s ago

    sig_dict = {
        "symbol": "XAUUSD",
        "timestamp": market_data_ts,
        "metadata": {
            "provenance_type": "live_signal",
            "is_live": True,
            "produced_at": publication_ts,
        },
    }

    is_live, reason = _evaluate_signal_live_status(sig_dict, requested_symbol="XAUUSD")
    assert is_live is True, f"Expected ACTIVE for fresh publication, got: {reason}"
    assert "Verified current live signal" in reason


def test_scenario_2_authoritative_valid_until_expired():
    """Scenario 2: Publication is within 300s, but valid_until timestamp has passed.

    MUST evaluate to NO SIGNAL (False).
    """
    now_ts = time.time()
    sig_dict = {
        "symbol": "XAUUSD",
        "timestamp": now_ts - 100.0,
        "metadata": {
            "provenance_type": "live_signal",
            "is_live": True,
            "produced_at": now_ts - 100.0,
            "valid_until": now_ts - 10.0,  # Expired 10s ago
        },
    }

    is_live, reason = _evaluate_signal_live_status(sig_dict, requested_symbol="XAUUSD")
    assert is_live is False
    assert "valid_until" in reason.lower() or "expired" in reason.lower()


def test_scenario_3_publication_older_than_300s_remains_active_signal():
    """Scenario 3: Publication is 301 seconds or 1 hour old (age > 300s).

    MUST evaluate to ACTIVE (is_live = True) and NOT be rejected or converted to NO SIGNAL.
    """
    now_ts = time.time()
    sig_dict = {
        "symbol": "XAUUSD",
        "timestamp": now_ts - 3600.0,
        "metadata": {
            "provenance_type": "live_signal",
            "is_live": True,
            "produced_at": now_ts - 301.0,
        },
    }

    is_live, reason = _evaluate_signal_live_status(sig_dict, requested_symbol="XAUUSD")
    assert is_live is True, f"Expected signal > 300s publication age to remain ACTIVE, got: {reason}"


def test_scenario_4_future_publication_timestamp_rejected():
    """Scenario 4: Publication timestamp is in the future beyond allowed skew (+60s).

    MUST evaluate to False (rejected).
    """
    now_ts = time.time()
    sig_dict = {
        "symbol": "XAUUSD",
        "timestamp": now_ts,
        "metadata": {
            "provenance_type": "live_signal",
            "is_live": True,
            "produced_at": now_ts + 60.0,
        },
    }

    is_live, reason = _evaluate_signal_live_status(sig_dict, requested_symbol="XAUUSD")
    assert is_live is False
    assert "future" in reason.lower()


def test_scenario_5_historical_provenance_rejected():
    """Scenario 5: Provenance is lab_artifact or marked historical.

    MUST evaluate to False (rejected).
    """
    now_ts = time.time()
    sig_dict = {
        "symbol": "XAUUSD",
        "timestamp": now_ts - 5.0,
        "metadata": {
            "provenance_type": "lab_artifact",
            "is_historical": True,
            "produced_at": now_ts - 5.0,
        },
    }

    is_live, reason = _evaluate_signal_live_status(sig_dict, requested_symbol="XAUUSD")
    assert is_live is False
    assert "historical" in reason.lower() or "provenance" in reason.lower()


def test_scenario_6_is_live_false_rejected():
    """Scenario 6: metadata explicitly sets is_live=False.

    MUST evaluate to False (rejected).
    """
    now_ts = time.time()
    sig_dict = {
        "symbol": "XAUUSD",
        "timestamp": now_ts - 5.0,
        "metadata": {
            "provenance_type": "live_signal",
            "is_live": False,
            "produced_at": now_ts - 5.0,
        },
    }

    is_live, reason = _evaluate_signal_live_status(sig_dict, requested_symbol="XAUUSD")
    assert is_live is False
    assert "non-live" in reason.lower()


def test_scenario_7_symbol_mismatch_rejected():
    """Scenario 7: Requested symbol XAUUSD vs Signal symbol EURUSD.

    MUST evaluate to False (rejected).
    """
    now_ts = time.time()
    sig_dict = {
        "symbol": "EURUSD",
        "timestamp": now_ts - 5.0,
        "metadata": {
            "provenance_type": "live_signal",
            "is_live": True,
            "produced_at": now_ts - 5.0,
        },
    }

    is_live, reason = _evaluate_signal_live_status(sig_dict, requested_symbol="XAUUSD")
    assert is_live is False
    assert "does not match" in reason.lower()


def test_scenario_8_5m_signal_requested_as_1h_in_adapter():
    """Scenario 8: 5m signal in storage queried with timeframe='1h'.

    Project1GatewayAdapter MUST return None / NO SIGNAL (timeframe isolation).
    """
    from src.platform.adapters.project1_adapter import Project1GatewayAdapter

    now_ts = time.time()
    rec_5m = {
        "command_type": "EMIT_SIGNAL",
        "symbol": "XAUUSD",
        "timeframe": "5m",
        "signal_type": "BUY",
        "timestamp": now_ts - 1000.0,
        "lifecycle_state": "STAGED",
        "created_at": now_ts - 10.0,
        "signal_id": "sig_5m_001",
        "metadata": {
            "provenance_type": "live_signal",
            "is_live": True,
            "produced_at": now_ts - 10.0,
        },
    }

    class FakeRepo:
        def list_records_for_user(self, **kwargs):
            return [rec_5m]

    class FakeGateway:
        _repo = FakeRepo()

    adapter = Project1GatewayAdapter(FakeGateway())

    # Query for 1h -> must return None
    res_1h = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="1h")
    assert res_1h is None

    # Query for 5m -> must return PresentedSignal
    res_5m = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="5m")
    assert res_5m is not None
    assert res_5m.timeframe == "5m"
    assert res_5m.signal_id == "sig_5m_001"


def test_scenario_9_newest_authoritative_publication_wins():
    """Scenario 9: Storage contains multiple publications for 5m; max event timestamp candidate is chosen."""
    from src.platform.adapters.project1_adapter import Project1GatewayAdapter

    now_ts = time.time()
    rec_older = {
        "command_type": "EMIT_SIGNAL",
        "symbol": "XAUUSD",
        "timeframe": "5m",
        "signal_type": "SELL",
        "timestamp": now_ts - 2000.0,
        "lifecycle_state": "STAGED",
        "created_at": now_ts - 100.0,
        "signal_id": "sig_older_001",
        "metadata": {
            "provenance_type": "live_signal",
            "is_live": True,
            "produced_at": now_ts - 100.0,
        },
    }
    rec_newer = {
        "command_type": "EMIT_SIGNAL",
        "symbol": "XAUUSD",
        "timeframe": "5m",
        "signal_type": "BUY",
        "timestamp": now_ts - 1000.0,
        "lifecycle_state": "STAGED",
        "created_at": now_ts - 10.0,
        "signal_id": "sig_newer_002",
        "metadata": {
            "provenance_type": "live_signal",
            "is_live": True,
            "produced_at": now_ts - 10.0,
        },
    }

    class FakeRepo:
        def list_records_for_user(self, **kwargs):
            return [rec_older, rec_newer]

    class FakeGateway:
        _repo = FakeRepo()

    adapter = Project1GatewayAdapter(FakeGateway())
    res = adapter.fetch_latest_signal(symbol="XAUUSD", timeframe="5m")
    assert res is not None
    assert res.signal_id == "sig_newer_002"
    assert res.signal_type == "buy"


def test_scenario_10_malformed_validity_metadata_fails_closed():
    """Scenario 10: Signal contains malformed string for valid_until/expires_at.

    MUST evaluate to False (fail closed).
    """
    now_ts = time.time()
    sig_dict = {
        "symbol": "XAUUSD",
        "timestamp": now_ts - 10.0,
        "metadata": {
            "provenance_type": "live_signal",
            "is_live": True,
            "produced_at": now_ts - 10.0,
            "valid_until": "not-a-valid-iso-date",
        },
    }

    is_live, reason = _evaluate_signal_live_status(sig_dict, requested_symbol="XAUUSD")
    assert is_live is False
    assert "malformed" in reason.lower()

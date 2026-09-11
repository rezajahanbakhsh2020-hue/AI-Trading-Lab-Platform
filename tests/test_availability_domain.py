import dataclasses
import math

import pytest

from src.platform.domain.availability import Availability, VALID_STATUSES


@pytest.mark.parametrize("status", list(VALID_STATUSES))
def test_valid_statuses(status):
    availability = Availability(status=status, timestamp="2026-09-11T00:00:00Z")
    assert availability.status == status


def test_status_is_normalized():
    availability = Availability(status=" LIVE ", timestamp=1)
    assert availability.status == "live"


def test_optional_fields_preserved():
    availability = Availability(
        status="stale",
        timestamp="2026-09-11T10:00:00Z",
        age_seconds=12,
        reason="quote marked stale by provider",
    )
    assert availability.timestamp == "2026-09-11T10:00:00Z"
    assert availability.age_seconds == 12.0
    assert availability.reason == "quote marked stale by provider"


def test_missing_optional_fields_remain_none():
    availability = Availability(status="unavailable")
    assert availability.timestamp is None
    assert availability.age_seconds is None
    assert availability.reason is None


@pytest.mark.parametrize("status", ["", "   ", "open", "unknown", 1, None])
def test_invalid_status_raises(status):
    with pytest.raises(ValueError):
        Availability(status=status)  # type: ignore[arg-type]


def test_blank_timestamp_string_raises():
    with pytest.raises(ValueError):
        Availability(status="live", timestamp="   ")


def test_non_finite_age_raises():
    with pytest.raises(ValueError):
        Availability(status="stale", age_seconds=math.inf)


def test_negative_age_raises():
    with pytest.raises(ValueError):
        Availability(status="stale", age_seconds=-1)


def test_blank_reason_raises():
    with pytest.raises(ValueError):
        Availability(status="offline", reason="   ")


def test_immutability():
    availability = Availability(status="live")
    with pytest.raises(dataclasses.FrozenInstanceError):
        availability.status = "stale"


def test_to_dict_preserves_values():
    availability = Availability(
        status="closed",
        timestamp=123,
        age_seconds=0,
        reason="market closed",
    )
    assert availability.to_dict() == {
        "status": "closed",
        "timestamp": 123,
        "age_seconds": 0.0,
        "reason": "market closed",
    }

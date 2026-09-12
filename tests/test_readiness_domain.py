import dataclasses

import pytest

from src.platform.domain.readiness import Readiness


def test_approved_readiness():
    readiness = Readiness(approved=True, timestamp=1)
    assert readiness.approved is True
    assert readiness.reason is None
    assert readiness.timestamp == 1


def test_rejected_readiness_preserves_reason():
    readiness = Readiness(
        approved=False,
        reason="strategy is not trade-ready",
        timestamp="2026-09-12T00:00:00Z",
    )
    assert readiness.approved is False
    assert readiness.reason == "strategy is not trade-ready"


def test_reason_is_trimmed():
    readiness = Readiness(approved=False, reason="  blocked  ")
    assert readiness.reason == "blocked"


@pytest.mark.parametrize("approved", [None, 1, 0, "true"])
def test_invalid_approved_raises(approved):
    with pytest.raises(ValueError):
        Readiness(approved=approved)  # type: ignore[arg-type]


def test_blank_reason_raises():
    with pytest.raises(ValueError):
        Readiness(approved=False, reason="   ")


def test_blank_timestamp_raises():
    with pytest.raises(ValueError):
        Readiness(approved=True, timestamp="  ")


def test_immutability():
    readiness = Readiness(approved=True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        readiness.approved = False


def test_to_dict():
    readiness = Readiness(approved=False, reason="blocked", timestamp=9)
    assert readiness.to_dict() == {
        "approved": False,
        "reason": "blocked",
        "timestamp": 9,
    }

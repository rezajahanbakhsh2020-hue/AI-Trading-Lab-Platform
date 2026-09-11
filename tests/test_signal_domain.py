import pytest

from src.platform.domain.signal import Signal


def test_valid_signal():
    signal = Signal(
        action="buy",
        strategy_name="TestStrategy",
        timestamp=1234567890,
        confidence=0.85,
    )

    assert signal.action == "buy"
    assert signal.strategy_name == "TestStrategy"
    assert signal.timestamp == 1234567890
    assert signal.confidence == 0.85


@pytest.mark.parametrize("action", ["buy", "sell", "hold", "no-signal"])
def test_valid_actions(action):
    signal = Signal(
        action=action,
        strategy_name="Strategy",
        timestamp=1,
    )

    assert signal.action == action


def test_action_normalization():
    assert Signal(
        action=" BUY ",
        strategy_name="Strategy",
        timestamp=1,
    ).action == "buy"

    assert Signal(
        action="NO_SIGNAL",
        strategy_name="Strategy",
        timestamp=1,
    ).action == "no-signal"


def test_strategy_name_is_trimmed():
    signal = Signal(
        action="buy",
        strategy_name="  Strategy  ",
        timestamp=1,
    )

    assert signal.strategy_name == "Strategy"


@pytest.mark.parametrize(
    "action",
    ["invalid", "", "long", "short", "buy_signal"],
)
def test_invalid_action(action):
    with pytest.raises(ValueError):
        Signal(
            action=action,
            strategy_name="Strategy",
            timestamp=1,
        )


@pytest.mark.parametrize(
    "strategy_name",
    ["", "   ", None],
)
def test_invalid_strategy_name(strategy_name):
    with pytest.raises(ValueError):
        Signal(
            action="buy",
            strategy_name=strategy_name,
            timestamp=1,
        )


@pytest.mark.parametrize(
    "confidence",
    [0.0, 0.5, 1.0],
)
def test_confidence_boundaries(confidence):
    signal = Signal(
        action="buy",
        strategy_name="Strategy",
        timestamp=1,
        confidence=confidence,
    )

    assert signal.confidence == confidence


@pytest.mark.parametrize(
    "confidence",
    [-0.01, 1.01, float("inf"), float("-inf"), float("nan")],
)
def test_invalid_confidence(confidence):
    with pytest.raises(ValueError):
        Signal(
            action="buy",
            strategy_name="Strategy",
            timestamp=1,
            confidence=confidence,
        )


def test_confidence_is_converted_to_float():
    signal = Signal(
        action="buy",
        strategy_name="Strategy",
        timestamp=1,
        confidence=1,
    )

    assert signal.confidence == 1.0
    assert isinstance(signal.confidence, float)


def test_none_confidence_is_allowed():
    signal = Signal(
        action="hold",
        strategy_name="Strategy",
        timestamp=1,
    )

    assert signal.confidence is None


@pytest.mark.parametrize(
    "timestamp",
    [0, 1, 1.5, "2026-01-01T00:00:00Z"],
)
def test_valid_timestamps(timestamp):
    signal = Signal(
        action="buy",
        strategy_name="Strategy",
        timestamp=timestamp,
    )

    assert signal.timestamp == timestamp


@pytest.mark.parametrize(
    "timestamp",
    [float("inf"), float("-inf"), float("nan"), ""],
)
def test_invalid_timestamp(timestamp):
    with pytest.raises(ValueError):
        Signal(
            action="buy",
            strategy_name="Strategy",
            timestamp=timestamp,
        )


def test_signal_is_immutable():
    signal = Signal(
        action="buy",
        strategy_name="Strategy",
        timestamp=1,
        confidence=0.5,
    )

    with pytest.raises((AttributeError, TypeError)):
        signal.action = "sell"


def test_signal_equality():
    first = Signal(
        action="buy",
        strategy_name="Strategy",
        timestamp=1,
        confidence=0.5,
    )
    second = Signal(
        action="buy",
        strategy_name="Strategy",
        timestamp=1,
        confidence=0.5,
    )

    assert first == second


def test_signal_hashability():
    signal = Signal(
        action="buy",
        strategy_name="Strategy",
        timestamp=1,
        confidence=0.5,
    )

    assert hash(signal) == hash(signal)


def test_signal_to_dict():
    signal = Signal(
        action="buy",
        strategy_name="Strategy",
        timestamp=123,
        confidence=0.75,
    )

    assert signal.to_dict() == {
        "action": "buy",
        "strategy_name": "Strategy",
        "timestamp": 123,
        "confidence": 0.75,
    }


def test_signal_to_dict_without_confidence():
    signal = Signal(
        action="hold",
        strategy_name="Strategy",
        timestamp=123,
    )

    assert signal.to_dict() == {
        "action": "hold",
        "strategy_name": "Strategy",
        "timestamp": 123,
        "confidence": None,
    }

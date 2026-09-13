"""Focused tests for Part 19 PresentedSignal and Project1IntegrationPort."""

import pytest

from src.platform.domain.presented_signal import PresentedSignal


def test_presented_signal_data_preservation():
    sig = PresentedSignal(
        signal_id="sig_101",
        symbol="XAUUSD",
        signal_type="buy",
        timestamp=1000.0,
        entry_price=2000.0,
        stop_loss=1990.0,
        take_profits=(2020.0, 2030.0, 2040.0),
        confidence=0.85,
        strategy_name="MomentumBreakout",
        timeframe="1h",
        metadata={"source": "Project1"},
    )

    assert sig.signal_id == "sig_101"
    assert sig.symbol == "XAUUSD"
    assert sig.signal_type == "buy"
    assert sig.timestamp == 1000.0
    assert sig.entry_price == 2000.0
    assert sig.stop_loss == 1990.0
    assert sig.take_profits == (2020.0, 2030.0, 2040.0)
    assert sig.confidence == 0.85
    assert sig.strategy_name == "MomentumBreakout"
    assert sig.timeframe == "1h"
    assert sig.metadata == {"source": "Project1"}


def test_presented_signal_tp_ordering_preserved():
    sig = PresentedSignal(
        signal_id="sig_102",
        symbol="EURUSD",
        signal_type="sell",
        timestamp=1000.0,
        take_profits=(1.0800, 1.0750, 1.0700),
    )

    assert sig.take_profits == (1.0800, 1.0750, 1.0700)


def test_presented_signal_optional_fields_not_fabricated():
    sig = PresentedSignal(
        signal_id="sig_103",
        symbol="BTCUSD",
        signal_type="buy",
        timestamp=1000.0,
    )

    assert sig.entry_price is None
    assert sig.stop_loss is None
    assert sig.take_profits == ()
    assert sig.confidence is None
    assert sig.strategy_name is None
    assert sig.timeframe is None


def test_presented_signal_validation():
    with pytest.raises(ValueError):
        PresentedSignal(signal_id="", symbol="XAUUSD", signal_type="buy", timestamp=100.0)

    with pytest.raises(ValueError):
        PresentedSignal(signal_id="1", symbol="XAUUSD", signal_type="invalid_type", timestamp=100.0)

    with pytest.raises(ValueError):
        PresentedSignal(signal_id="1", symbol="XAUUSD", signal_type="buy", timestamp=-10.0)

    with pytest.raises(ValueError):
        PresentedSignal(
            signal_id="1", symbol="XAUUSD", signal_type="buy", timestamp=100.0, confidence=1.5
        )


def test_presented_signal_to_dict():
    sig = PresentedSignal(
        signal_id="sig_104",
        symbol="XAUUSD",
        signal_type="buy",
        timestamp=1000.0,
        take_profits=(2020.0, 2030.0),
    )
    d = sig.to_dict()
    assert d["signal_id"] == "sig_104"
    assert d["symbol"] == "XAUUSD"
    assert d["take_profits"] == [2020.0, 2030.0]

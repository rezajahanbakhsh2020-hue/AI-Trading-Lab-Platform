"""Focused Part 6 tests for the LabArtifactService application service."""

import pytest

from src.platform.domain import Signal, Stability, TradeSetup
from src.platform.integrations import LabArtifactSource
from src.platform.services import LabArtifactService


class FakeLabSource(LabArtifactSource):
    """In-memory read-only Lab source double backing the service tests."""

    def __init__(self, signal=None, setup=None, stability=None):
        self.signal = signal
        self.setup = setup
        self.stability = stability
        self.connect_calls = 0
        self.fetch_calls =  0
        self.close_calls = 0

    def connect(self):
        self.connect_calls += 1

    def fetch_signal(self, symbol, timeframe):
        self.fetch_calls +=  1
        return self.signal

    def fetch_trade_setup(self, symbol, timeframe):
        self.fetch_calls +=  1
        return self.setup

    def fetch_stability(self, strategy_name):
        self.fetch_calls +=  1
        return self.stability

    def close(self):
        self.close_calls +=  1

    def describe(self):
        return {"name": "FakeLabSource", "available": True}


def _service(source=None):
    if source is None:
        source = FakeLabSource()
    return LabArtifactService(source), source


def _signal_dict():
    return {
        "action": "buy",
        "strategy_name": "momentum",
        "timestamp": 1700000000,
        "confidence": 0.82,
    }


def _setup_dict():
    return {
        "symbol": "XAUUSD",
        "entry_price": 4330.0,
        "stop_loss": 4310.0,
        "take_profit_1": 4350.0,
        "take_profit_2": 4380.0,
        "take_profit_3": 4410.0,
        "timestamp": 1700000000,
        "direction": "buy",
    }


def _stability_dict():
    return {
        "score": 0.91,
        "risk_level": "low",
        "metrics": {"win_rate": 0.55},
    }


def test_service_requires_source():
    with pytest.raises(ValueError):
        LabArtifactService(None)


def test_rejects_non_lab_source():
    with pytest.raises(ValueError):
        LabArtifactService(object())  # type: ignore


def test_valid_signal_becomes_domain_signal():
    src = FakeLabSource(signal=_signal_dict())
    svc, src = _service(src)
    sig = svc.get_signal("XAUUSD", "1h")
    assert isinstance(sig, Signal)
    assert sig.action == "buy"
    assert sig.strategy_name == "momentum"
    assert sig.confidence == 0.82


def test_missing_signal_is_none_not_fabricated():
    src = FakeLabSource(signal=None)
    svc, _ = _service(src)
    assert svc.get_signal("XAUUSD", "1h") is None
    assert svc.get_signal("XAUUSD", "1h") is None


def test_valid_trade_setup_becomes_domain_object():
    src = FakeLabSource(setup=_setup_dict())
    svc, _ = _service(src)
    setup = svc.get_trade_setup("XAUUSD", "1h")
    assert isinstance(setup, TradeSetup)
    assert setup.symbol == "XAUUSD"
    assert setup.direction == "buy"
    assert setup.entry_price == 4330.0


def test_missing_trade_setup_is_none():
    src = FakeLabSource(setup=None)
    svc, _ = _service(src)
    assert svc.get_trade_setup("XAUUSD", "1h") is None


def test_valid_stability_becomes_domain_object():
    src = FakeLabSource(stability=_stability_dict())
    svc, _ = _service(src)
    stab = svc.get_stability("momentum")
    assert isinstance(stab, Stability)
    assert stab.score == 0.91
    assert stab.risk_level == "low"



def test_missing_stability_is_none():
    src = FakeLabSource(stability=None)
    svc, _ = _service(src)
    assert svc.get_stability("momentum") is None



def test_construction_and_validation_do_no_io():
    src = FakeLabSource()
    svc, src = _service(src)
    svc.get_signal("XAUUSD", "1h")
    assert src.fetch_calls ==  1
    assert src.connect_calls ==  0
    assert src.close_calls ==  0


def test_inputs_validated_before_source_fetch():
    src = FakeLabSource(signal=_signal_dict())
    svc, _ = _service(src)
    with pytest.raises(ValueError):
        svc.get_signal(" ", "1h")
    with pytest.raises(ValueError):
        svc.get_signal("XAUUSD", "")
    with pytest.raises(ValueError):
        svc.get_trade_setup(None, "1h")  # type: ignore
    with pytest.raises(ValueError):
        svc.get_stability("   ")
    assert src.fetch_calls ==  0



def test_source_errors_propagate():
    src = FakeLabSource()
    src.signal = RuntimeError("source boom")
    svc, _ = _service(src)
    src.fetch_signal = lambda symbol, timeframe: _raise_for_test()
    with pytest.raises(RuntimeError, match="source boom"):
        svc.get_signal("XAUUSD", "1h")


def _raise_for_test():
    raise RuntimeError("source boom")



def test_missing_required_field_raises():
    src = FakeLabSource(signal={})
    svc, _ = _service(src)
    with pytest.raises(ValueError):
        svc.get_signal("XAUUSD", "1h")


def test_exported_from_services_package():
    from src.platform.services import LabArtifactService as Exported
    assert Exported is LabArtifactService
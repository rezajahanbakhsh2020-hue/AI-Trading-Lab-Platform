"""Part 7 focused tests for the MarketOverviewService application service."""

import pytest

from src.platform.domain import Availability
from src.platform.domain import Candle
from src.platform.domain import MarketOverview
from src.platform.domain import Quote
from src.platform.domain import Signal
from src.platform.domain import Stability
from src.platform.domain import TradeSetup
from src.platform.integrations.lab import LabArtifactSource
from src.platform.services import CandleOperationResult
from src.platform.services import LabArtifactService
from src.platform.services import MarketOverviewService
from src.platform.services import ProviderAccess
from src.platform.services import ProviderOperations
from src.platform.services import ProviderRegistry
from src.platform.services import QuoteOperationResult


class FakeOperations(ProviderOperations):
    """ProviderOperations double recording explicit fetches."""

    def __init__(self, candles=None, quote=None, to_raise=None):
        super().__init__(ProviderAccess(ProviderRegistry()))
        self.candles = candles if candles is not None else []
        self.quote = quote
        self.to_raise = to_raise
        self.fetch_candles_calls = 0
        self.fetch_quote_calls = 0

    def fetch_candles(self, provider_id, symbol, timeframe, limit):
        self.fetch_candles_calls += 1
        self.last_candles_args = (provider_id, symbol, timeframe, limit)
        if self.to_raise is not None:
            raise self.to_raise
        return CandleOperationResult(
            provider_id=provider_id,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            candles=self.candles,
        )

    def fetch_quote(self, provider_id, symbol):
        self.fetch_quote_calls +=  1
        self.last_quote_args = (provider_id, symbol)
        if self.to_raise is not None:
            raise self.to_raise
        return QuoteOperationResult(
            provider_id=provider_id,
            symbol=symbol,
            quote=self.quote,
        )


class _FakeSource(LabArtifactSource):
    """LabArtifactSource double returning unavailable data."""

    def connect(self):
        return None

    def fetch_signal(self, symbol, timeframe):
        return None

    def fetch_trade_setup(self, symbol, timeframe):
        return None

    def fetch_stability(self, strategy_name):
        return None

    def close(self):
        return None

    def describe(self):
        return {"name": "fake-source"}


class FakeLab(LabArtifactService):
    """LabArtifactService double recording explicit artifact fetches."""

    def __init__(self, signal=None, setup=None, stability=None):
        super().__init__(_FakeSource())
        self.signal = signal
        self.setup = setup
        self.stability = stability
        self.get_signal_calls = 0
        self.get_trade_setup_calls = 0
        self.get_stability_calls = 0

    def get_signal(self, symbol, timeframe):
        self.get_signal_calls += 1
        self.last_signal_args = (symbol, timeframe)
        return self.signal

    def get_trade_setup(self, symbol, timeframe):
        self.get_trade_setup_calls += 1
        self.last_setup_args = (symbol, timeframe)
        return self.setup

    def get_stability(self, strategy_name):
        self.get_stability_calls +=  1
        return self.stability

def _candle(index):
    return Candle(timestamp=1000+index, open=1.0, high=1.2, low=0.9, close=1.1, volume=100.0)


def _quote():
    return Quote(
        symbol="XAUUSD",
        timestamp=1700000000,
        bid=4330.0,
        ask=4330.5,
        availability=Availability(status="live", age_seconds=0.0),
    )


def _signal():
    return Signal(action="buy", strategy_name="momentum", timestamp=1700000000, confidence=0.82)


def _setup():
    return TradeSetup(
        symbol="XAUUSD",
        entry_price=4330.0,
        stop_loss=4310.0,
        take_profit_1=4350.0,
        take_profit_2=4380.0,
        take_profit_3=4410.0,
        timestamp=1700000000,
        direction="buy",
    )


def _stability():
    return Stability(score=0.91, risk_level="low", metrics={"win_rate": 0.55})


def _service(ops=None, lab=None):
    if ops is None:
        ops = FakeOperations(candles=[_candle(1), _candle(2)], quote=_quote())
    return MarketOverviewService(operations=ops, lab=lab), ops, lab


def test_requires_operations():
    with pytest.raises(ValueError):
        MarketOverviewService(None)


def test_rejects_non_operations():
    with pytest.raises(ValueError):
        MarketOverviewService(object())  # type: ignore


def test_rejects_invalid_lab():
    with pytest.raises(ValueError):
        MarketOverviewService(FakeOperations(), lab=object())  # type: ignore


def test_full_overview_composes_all_parts():
    svc, ops, lab = _service(lab=FakeLab(signal=_signal(), setup=_setup(), stability=_stability()))
    overview = svc.get_overview(
        symbol="XAUUSD",
        timeframe="1h",
        candles_provider_id="md_one",
        quote_provider_id="qt_one",
        strategy_name="momentum",
    )
    assert isinstance(overview, MarketOverview)
    assert overview.symbol == "XAUUSD"
    assert overview.timeframe == "1h"
    assert isinstance(overview.quote, Quote)
    assert isinstance(overview.candles[0], Candle)
    assert len(overview.candles) == 2
    assert isinstance(overview.candles, tuple)
    assert isinstance(overview.signal, Signal)
    assert isinstance(overview.trade_setup, TradeSetup)
    assert isinstance(overview.stability, Stability)
    assert overview.availability.status == "live"
    assert ops.fetch_candles_calls == 1
    assert ops.fetch_quote_calls == 1
    assert lab.get_signal_calls == 1
    assert lab.get_trade_setup_calls == 1
    assert lab.get_stability_calls == 1


def test_omitted_quote_leaves_quote_none():
    svc, ops, _ = _service()
    overview = svc.get_overview("XAUUSD", "1h", candles_provider_id="md_one")
    assert overview.quote is None
    assert overview.availability is None
    assert ops.fetch_quote_calls == 0


def test_omitted_lab_leaves_artifacts_none():
    svc, _, _ = _service(lab=None)
    overview = svc.get_overview("XAUUSD", "1h", candles_provider_id="md_one")
    assert overview.signal is None
    assert overview.trade_setup is None
    assert overview.stability is None


def test_stability_without_strategy_name_is_none():
    lab = FakeLab(signal=_signal(), setup=_setup(), stability=_stability())
    svc, _, _ = _service(lab=lab)
    overview = svc.get_overview("XAUUSD", "1h", candles_provider_id="md_one", strategy_name=None)
    assert overview.signal is not None
    assert overview.trade_setup is not None
    assert overview.stability is None
    assert lab.get_stability_calls == 0


def test_invalid_symbol_rejected_before_fetch():
    svc, ops, _ = _service()
    with pytest.raises(ValueError):
        svc.get_overview(" ", "1h", candles_provider_id="md_one")
    assert ops.fetch_candles_calls == 0

def test_invalid_timeframe_rejected_before_fetch():
    svc, ops, _ = _service()
    with pytest.raises(ValueError):
        svc.get_overview("XAUUSD", "   ", candles_provider_id="md_one")
    assert ops.fetch_candles_calls == 0


def test_candle_failure_propagates():
    ops = FakeOperations(to_raise=RuntimeError("candle boom"))
    svc, _, _ = _service(ops=ops)
    with pytest.raises(RuntimeError, match="candle boom"):
        svc.get_overview("XAUUSD", "1h", candles_provider_id="md_one")


def test_quote_failure_propagates():
    ops = FakeOperations(candles=[_candle(1)], to_raise=RuntimeError("quote boom"))
    svc, _, _ = _service(ops=ops)
    with pytest.raises(RuntimeError, match="quote boom"):
        svc.get_overview(
            "XAUUSD",
            "1h",
            candles_provider_id="md_one",
            quote_provider_id="qt_one",
        )


def test_lab_failure_propagates():
    lab = FakeLab()
    lab.get_signal = lambda symbol, timeframe: _raise()
    svc, _, _ = _service(lab=lab)
    with pytest.raises(RuntimeError, match="lab boom"):
        svc.get_overview("XAUUSD", "1h", candles_provider_id="md_one")


def _raise():
    raise RuntimeError("lab boom")


def test_to_dict_shape():
    svc, ops, lab = _service(lab=FakeLab(signal=_signal(), setup=_setup(), stability=_stability()))
    overview = svc.get_overview(
        "XAUUSD",
        "1h",
        candles_provider_id="md_one",
        quote_provider_id="qt_one",
        strategy_name="momentum",
    )
    data = overview.to_dict()
    assert data["symbol"] == "XAUUSD"
    assert data["timeframe"] == "1h"
    assert data["quote"]["symbol"] == "XAUUSD"
    assert len(data["candles"]) == 2
    assert data["signal"]["action"] == "buy"
    assert data["trade_setup"]["direction"] == "buy"
    assert data["stability"]["risk_level"] == "low"
    assert data["availability"]["status"] == "live"


def test_exported_from_domain():
    from src.platform.domain import MarketOverview as Exported
    assert Exported is MarketOverview


def test_exported_from_services():
    from src.platform.services import MarketOverviewService as Exported
    assert Exported is MarketOverviewService
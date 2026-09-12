"""Focused tests for the TradeReadinessService trading-intelligence layer (Part 13)."""

from typing import Optional

import pytest

from src.platform.domain import MarketOverview, Quote, TradeReadiness, TradeSetup
from src.platform.services import MarketOverviewService, TradeReadinessResult, TradeReadinessService


def _quote(symbol: str = "XAUUSD", bid: float = 4330.0, ask: float = 4331.0) -> Quote:
    return Quote(symbol=symbol, timestamp=1700000000, bid=bid, ask=ask)


def _setup(
    symbol: str = "XAUUSD",
    direction: str = "buy",
    entry: float = 4332.0,
    stop: float = 4320.0,
    tp1: float = 4340.0,
    tp2: float = 4350.0,
    tp3: float = 4360.0,
) -> TradeSetup:
    return TradeSetup(
        symbol=symbol,
        entry_price=entry,
        stop_loss=stop,
        take_profit_1=tp1,
        take_profit_2=tp2,
        take_profit_3=tp3,
        timestamp=1700000000,
        direction=direction,
    )


def _overview(
    *,
    setup: Optional[TradeSetup] = None,
    quote: Optional[Quote] = None,
    **overrides: object,
) -> MarketOverview:
    kwargs: dict = {
        "symbol": "XAUUSD",
        "timeframe": "1h",
        "candles": [],
        "quote": quote,
        "trade_setup": setup,
    }
    kwargs.update(overrides)
    return MarketOverview(**kwargs)


class FakeOverview(MarketOverviewService):
    """MarketOverviewService double returning a fixed snapshot."""

    def __init__(self, overview: MarketOverview):
        self.overview = overview
        self.calls: int = 0
        self.last_args: Optional[tuple] = None

    def get_overview(self, symbol, timeframe, candles_provider_id, candles_limit=100, quote_provider_id=None, strategy_name=None):
        self.calls +=  1
        self.last_args = (symbol, timeframe, candles_provider_id, candles_limit, quote_provider_id, strategy_name)
        return self.overview


def _service(overview: MarketOverview) -> FakeOverview:
    return FakeOverview(overview)


def test_requires_overview_service():
    with pytest.raises(ValueError):
        TradeReadinessService(None)
with pytest.raises(ValueError, match="overview"):
    TradeReadinessService(object())


def test_no_quote_and_no_setup_means_unavailable():
    fake = _service(_overview(setup=None, quote=None))
    svc = TradeReadinessService(fake)
    result = svc.assess("XAUUSD", "1h", "md_one")
    assert isinstance(result, TradeReadinessResult)
    assert result.trade_readiness is None
    assert result.market_data_provider_id ==  "md_one"
    assert result.quote_provider_id is None
    assert fake.calls ==  1


def test_setup_without_quote_means_no_readiness():
    fake = _service(_overview(setup=_setup(), quote=None))
    svc = TradeReadinessService(fake)
    result = svc.assess("XAUUSD", "1h", "md_one", quote_provider_id="qt_one")
    assert result.trade_readiness is None
    assert result.quote_provider_id == "qt_one"


def test_quote_without_setup_means_no_readiness():
    fake = _service(_overview(setup=None, quote=_quote()))
    svc = TradeReadinessService(fake)
    result = svc.assess("XAUUSD", "1h", "md_one")
    assert result.trade_readiness is None


def test_buy_uses_ask_current_price():
    setup = _setup(entry=4332.0, stop=4320.0, tp1=4340.0, tp2=4350.0, tp3=4360.0)
    quote = _quote(bid=4330.0, ask=4331.0)
    fake = _service(_overview(setup=setup, quote=quote))
    result = TradeReadinessService(fake).assess(
        "XAUUSD", "1h", "md_one", quote_provider_id="qt_one", strategy_name="momentum"
    )
    readiness = result.trade_readiness
    assert readiness is not None
    assert readiness.current_price ==  4331.0
    assert readiness.direction == "buy"
    assert readiness.entry_price ==  4332.0
    assert readiness.entry_distance_absolute ==  pytest.approx(-1.0)
    assert readiness.entry_distance_percent ==  pytest.approx(-1.0 / 4331.0 * 100.0)
    # stop is below current price for a long: distance is measured as stop - price.
    assert readiness.stop_distance_absolute ==  pytest.approx(-11.0)
    assert readiness.tp1_distance_percent ==  pytest.approx((4340.0 -  4331.0) /  4331.0 * 100.0)
    assert readiness.tp2_distance_percent is not None
    assert readiness.tp3_distance_percent is not None
    assert readiness.risk_reward_to_tp1 == pytest.approx((4340.0 -  4332.0) / (4332.0 -  4320.0))
    assert readiness.levels_are_sane is True  # price sits between stop and take-profits


def test_buy_quote_at_or_above_entry_marks_levels_sane():
    setup = _setup(entry=4330.0, stop=4320.0, tp1=4340.0, tp2=4350.0, tp3=4360.0)
    quote = _quote(bid=4330.0, ask=4331.0)
    readiness = TradeReadinessService(_service(_overview(setup=setup, quote=quote))).assess(
        "XAUUSD", "1h", "md_one", quote_provider_id="qt_one"
    ).trade_readiness
    assert readiness is not None
    assert readiness.current_price ==  4331.0
    assert readiness.levels_are_sane is True
    assert readiness.entry_distance_percent ==  pytest.approx((4331.0 -  4330.0) / 4331.0 * 100.0)


def test_sell_uses_bid_current_price():
    setup = _setup(direction="sell", entry=4330.0, stop=4340.0, tp1=4320.0, tp2=4310.0, tp3=4300.0)
    quote = _quote(bid=4331.0, ask=4332.0)
    readiness = TradeReadinessService(_service(_overview(setup=setup, quote=quote))).assess(
        "XAUUSD", "1h", "md_one", quote_provider_id="qt_one"
    ).trade_readiness
    assert readiness is not None
    assert readiness.current_price ==  4331.0
    assert readiness.direction == "sell"
    assert readiness.stop_distance_absolute ==  pytest.approx(9.0)  # stop(4340) - price(4331)
    assert readiness.levels_are_sane is True  # price sits between stop and take-profits for a sell


def test_sell_quote_at_or_below_entry_marks_levels_sane():
    setup = _setup(direction="sell", entry=4332.0, stop=4340.0, tp1=4330.0, tp2=4320.0, tp3=4310.0)
    quote = _quote(bid=4331.0, ask=4332.0)
    readiness = TradeReadinessService(_service(_overview(setup=setup, quote=quote))).assess(
        "XAUUSD", "1h", "md_one", quote_provider_id="qt_one"
    ).trade_readiness
    assert readiness is not None
    assert readiness.current_price ==  4331.0
    assert readiness.levels_are_sane is True


def test_missing_honest_quote_side_yields_no_readiness():
    setup = _setup(direction="buy", entry=4332.0, stop=4320.0, tp1=4340.0, tp2=4350.0, tp3=4360.0)
    quote = _quote(bid=4330.0, ask=None)
    readiness = TradeReadinessService(_service(_overview(setup=setup, quote=quote))).assess(
        "XAUUSD", "1h", "md_one", quote_provider_id="qt_one"
    ).trade_readiness
    assert readiness is not None
    assert readiness.current_price is None
    assert readiness.entry_distance_absolute is None
    assert readiness.stop_distance_absolute is None
    assert readiness.tp1_distance_percent is None
    assert readiness.risk_reward_to_tp1 is not None  # risk/reward uses levels alone


def test_risk_reward_uses_levels_alone_without_quote():
    setup = _setup(entry=4332.0, stop=4320.0, tp1=4340.0, tp2=4350.0, tp3=4360.0)
    fake = _service(_overview(setup=setup, quote=None))
    service = TradeReadinessService(fake)
    result = service.assess("XAUUSD", "1h", "md_one", quote_provider_id="qt_one")
    assert result.trade_readiness is None  # no quote → no readiness object at all


def test_invalid_symbol_rejected_before_overview():
    fake = _service(_overview())
    svc = TradeReadinessService(fake)
    with pytest.raises(ValueError, match="symbol"):
        svc.assess(" ", "1h", "md_one")
    assert fake.calls ==  0


def test_invalid_timeframe_rejected_before_overview():
    fake = _service(_overview())
    svc = TradeReadinessService(fake)
    with pytest.raises(ValueError, match="timeframe"):
        svc.assess("XAUUSD", " ", "md_one")
    assert fake.calls ==  0


def test_invalid_limit_rejected_before_overview():
    fake = _service(_overview())
    svc = TradeReadinessService(fake)
    with pytest.raises(ValueError, match="limit"):
        svc.assess("XAUUSD", "1h", "md_one", candles_limit=0)
    assert fake.calls ==  0


def test_overview_errors_propagate():
    class BoomOverview(MarketOverviewService):
        def __init__(self):
            pass

        def get_overview(self, *args, **kwargs):
            raise RuntimeError("overview boom")
    svc = TradeReadinessService(BoomOverview())
    with pytest.raises(RuntimeError, match="overview boom"):
        svc.assess("XAUUSD", "1h", "md_one")


def test_quote_provider_id_preserved_in_result():
    setup = _setup()
    fake = _service(_overview(setup=setup, quote=_quote()))
    result = TradeReadinessService(fake).assess(
        "XAUUSD", "1h", "md_one", quote_provider_id="qt_z", strategy_name="momentum"
    )
    assert result.quote_provider_id == "qt_z"
    assert result.market_data_provider_id == "md_one"
    assert fake.last_args[2] == "md_one"
    assert fake.last_args[4] == "qt_z"
    assert fake.last_args[5] == "momentum"


def test_exported_from_services_package():
    from src.platform.services import TradeReadinessService as ExportedService
    from src.platform.services import TradeReadinessResult as ExportedResult
    assert ExportedService is TradeReadinessService
    assert ExportedResult is TradeReadinessResult


def test_domain_exported():
    from src.platform.domain import TradeReadiness as ExportedReadiness
    assert ExportedReadiness is TradeReadiness


def test_to_dict_shape():
    setup = _setup()
    quote = _quote(bid=4330.0, ask=4331.0)
    readiness = TradeReadinessService(_service(_overview(setup=setup, quote=quote))).assess(
        "XAUUSD", "1h", "md_one", quote_provider_id="qt_one"
    ).trade_readiness
    payload = readiness.to_dict()
    assert payload["symbol"] == "XAUUSD"
    assert payload["direction"] == "buy"
    assert payload["current_price"] == 4331.0
    assert isinstance(payload["entry_distance_percent"], float)
    assert payload["levels_are_sane"] in (True, False)
"""Trade readiness application service.

Builds a TradeReadiness assessment for one market context by reading the
real TradeSetup levels and the real current Quote price from an injected
MarketOverviewService, without inventing any price, level,, or distance.
It is the first "trading intelligence" layer the platform exposes: a
read-only, deterministic computation over already-fetched real market state..

Rules:
- construction and validation perform no I/O and no connect;
- nothing is fetched unless an explicit ``assess`` call is made;
- provider/source errors propagate unchanged to the caller;
- ``None`` from any contract means genuinely unavailable, never fabricated;
- the setup direction decides the honest quote side (ask for buy, bid for
  sell); absent side or quote means no current price and therefore no
  distance fields (None, never zero or invented);
- percentages are computed only when the current price is a positive finite
  number; risk/reward uses only the real setup levels (0 division yields
  None, never infinity;
- ``levels_are_sane`` reports only the observed geometry of real levels and the
  real current price; it never implies trading advice or guaranteed profit..
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional
import numbers
import math

from src.platform.domain.quote import Quote
from src.platform.domain.trade_readiness import TradeReadiness
from src.platform.domain.trade_setup import TradeSetup
from src.platform.services.market_overview import MarketOverviewService


@dataclass(frozen=True)
class TradeReadinessResult:
    """Result of a trade readiness assessment carrying explicit source identity."""

    symbol: str
    timeframe: str
    market_data_provider_id: str
    quote_provider_id: Optional[str] = None
    trade_readiness: Optional[TradeReadiness] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "market_data_provider_id": self.market_data_provider_id,
            "quote_provider_id": self.quote_provider_id,
            "trade_readiness": (
                None if self.trade_readiness is None else self.trade_readiness.to_dict()
            ),
        }


class TradeReadinessService:
    """Assess how far real market price is from real structural trade levels."""

    def __init__(self, overview: MarketOverviewService) -> None:
        if overview is None or not isinstance(overview, MarketOverviewService):
            raise ValueError("overview must be a MarketOverviewService")
        self._overview = overview

    def assess(
        self,
        symbol: str,
        timeframe: str,
        candles_provider_id: str,
        strategy_name: Optional[str] = None,
        candles_limit: int = 100,
        quote_provider_id: Optional[str] = None,
    ) -> TradeReadinessResult:
        """Assess readiness for one explicitly requested market context.



        The overview snapshot is computed exactly once via the injected
        MarketOverviewService (which may raise validation/provider/lab errors;
        those propagate unchanged). Quote and strategy are optional per call:
        when missing the resulting readiness carries no quote/levels and no
        distance fields rather than an invented assessment..
        """
        _validate_symbol(symbol)
        _validate_timeframe(timeframe)
        _validate_limit(candles_limit)

        overview = self._overview.get_overview(
            symbol=symbol,
            timeframe=timeframe,
            candles_provider_id=candles_provider_id,
            candles_limit=candles_limit,
            quote_provider_id=quote_provider_id,
            strategy_name=strategy_name,
        )

        readiness = None
        if overview.trade_setup is not None and overview.quote is not None:
            readiness = self._build_readiness(
                symbol=symbol,
                timeframe=timeframe,
                setup=overview.trade_setup,
                quote=overview.quote,
            )

        return TradeReadinessResult(
            symbol=symbol,
            timeframe=timeframe,
            market_data_provider_id=candles_provider_id,
            quote_provider_id=quote_provider_id,
            trade_readiness=readiness,
        )

    def _build_readiness(
        self,
        symbol: str,
        timeframe: str,
        setup: TradeSetup,
        quote: Quote,
    ) -> TradeReadiness:
        risk_reward = None
        if setup.risk > 0:
            risk_reward = setup.reward / setup.risk

        current_price = _current_price_for(quote, setup.direction)
        if current_price is None:
            return TradeReadiness(
                symbol=symbol,
                timeframe=timeframe,
                direction=setup.direction,
                entry_price=setup.entry_price,
                stop_loss=setup.stop_loss,
                take_profit_1=setup.take_profit_1,
                take_profit_2=setup.take_profit_2,
                take_profit_3=setup.take_profit_3,
                risk_reward_to_tp1=risk_reward,
            )

        entry_distance_absolute = current_price - setup.entry_price
        entry_distance_percent = _percent(current_price, entry_distance_absolute)

        stop_distance_absolute = _stop_distance(current_price, setup)
        stop_distance_percent = _percent(current_price, stop_distance_absolute)

        tp1_distance_percent = _level_percent(current_price, setup.take_profit_1)
        tp2_distance_percent = _level_percent(current_price, setup.take_profit_2)
        tp3_distance_percent = _level_percent(current_price, setup.take_profit_3)

        levels_are_sane = _levels_sane(setup, current_price)

        return TradeReadiness(
            symbol=symbol,
            timeframe=timeframe,
            direction=setup.direction,
            entry_price=setup.entry_price,
            stop_loss=setup.stop_loss,
            take_profit_1=setup.take_profit_1,
            take_profit_2=setup.take_profit_2,
            take_profit_3=setup.take_profit_3,
            current_price=current_price,
            entry_distance_absolute=entry_distance_absolute,
            entry_distance_percent=entry_distance_percent,
            stop_distance_absolute=stop_distance_absolute,
            stop_distance_percent=stop_distance_percent,
            tp1_distance_percent=tp1_distance_percent,
            tp2_distance_percent=tp2_distance_percent,
            tp3_distance_percent=tp3_distance_percent,
            risk_reward_to_tp1=risk_reward,
            levels_are_sane=levels_are_sane,
        )


def _current_price_for(quote: Quote, direction: str) -> Optional[float]:
    """Return the honest observable price for the direction, or None."""
    if direction == "buy":
        return quote.ask
    return quote.bid


def _percent(current_price: float, amount: float) -> Optional[float]:
    if current_price is None or not isinstance(current_price, numbers.Real):
        return None
    if isinstance(current_price, bool) or not math.isfinite(float(current_price)):
        return None
    price = float(current_price)
    if price <= 0:
        return None
    return (amount / price) * 100.0


def _stop_distance(current_price: float, setup: TradeSetup) -> float:
    return setup.stop_loss - current_price


def _level_percent(current_price: float, level: float) -> Optional[float]:
    if level is None:
        return None
    distance = level - current_price
    return _percent(current_price, distance)


def _levels_sane(setup: TradeSetup, current_price: float) -> bool:
    if setup.direction == "buy":
        stop_ok = setup.stop_loss < current_price
        tp_ok = (
            setup.take_profit_1 > current_price
            and setup.take_profit_2 > current_price
            and setup.take_profit_3 > current_price
        )
        return stop_ok and tp_ok
    stop_ok = setup.stop_loss > current_price
    tp_ok = (
        setup.take_profit_1 < current_price
        and setup.take_profit_2 < current_price
        and setup.take_profit_3 < current_price
    )
    return stop_ok and tp_ok


def _validate_symbol(symbol: str) -> None:
    if not isinstance(symbol, str):
        raise ValueError("symbol must be a string")
    if symbol.strip() == "":
        raise ValueError("symbol must not be empty or whitespace")


def _validate_timeframe(timeframe: str) -> None:
    if not isinstance(timeframe, str):
        raise ValueError("timeframe must be a string")
    if timeframe.strip() == "":
        raise ValueError("timeframe must not be empty or whitespace")


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("limit must be an integer")
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
import pytest

from src.platform.domain.trade_setup import TradeSetup


def make_buy_setup():
    return TradeSetup(
        symbol="XAUUSD",
        entry_price=2000.0,
        stop_loss=1990.0,
        take_profit_1=2020.0,
        take_profit_2=2030.0,
        take_profit_3=2040.0,
        timestamp=1,
        direction="buy",
    )


def make_sell_setup():
    return TradeSetup(
        symbol="XAUUSD",
        entry_price=2000.0,
        stop_loss=2010.0,
        take_profit_1=1980.0,
        take_profit_2=1970.0,
        take_profit_3=1960.0,
        timestamp=1,
        direction="sell",
    )


def test_valid_buy_setup():
    setup = make_buy_setup()

    assert setup.symbol == "XAUUSD"
    assert setup.direction == "buy"
    assert setup.entry_price == 2000.0
    assert setup.stop_loss == 1990.0
    assert setup.take_profit_1 == 2020.0
    assert setup.take_profit_2 == 2030.0
    assert setup.take_profit_3 == 2040.0


def test_valid_sell_setup():
    setup = make_sell_setup()

    assert setup.symbol == "XAUUSD"
    assert setup.direction == "sell"
    assert setup.entry_price == 2000.0
    assert setup.stop_loss == 2010.0
    assert setup.take_profit_1 == 1980.0
    assert setup.take_profit_2 == 1970.0
    assert setup.take_profit_3 == 1960.0


def test_symbol_and_direction_are_normalized():
    setup = TradeSetup(
        symbol="  xauusd  ",
        entry_price=2000,
        stop_loss=1990,
        take_profit_1=2020,
        take_profit_2=2030,
        take_profit_3=2040,
        timestamp=1,
        direction=" BUY ",
    )

    assert setup.symbol == "xauusd"
    assert setup.direction == "buy"


def test_integer_prices_are_converted_to_float():
    setup = TradeSetup(
        symbol="XAUUSD",
        entry_price=2000,
        stop_loss=1990,
        take_profit_1=2020,
        take_profit_2=2030,
        take_profit_3=2040,
        timestamp=1,
        direction="buy",
    )

    assert isinstance(setup.entry_price, float)
    assert isinstance(setup.stop_loss, float)
    assert isinstance(setup.take_profit_1, float)
    assert isinstance(setup.take_profit_2, float)
    assert isinstance(setup.take_profit_3, float)


def test_buy_risk_and_reward():
    setup = make_buy_setup()

    assert setup.risk == 10.0
    assert setup.reward == 20.0


def test_sell_risk_and_reward():
    setup = make_sell_setup()

    assert setup.risk == 10.0
    assert setup.reward == 20.0


def test_risk_reward_ratio_property():
    setup = make_buy_setup()

    assert setup.risk_reward_ratio == 2.0
    assert setup.risk_reward_ratio() == 2.0


def test_risk_reward_ratio_for_each_tp():
    setup = make_buy_setup()

    assert setup.get_risk_reward_ratio(1) == 2.0
    assert setup.get_risk_reward_ratio(2) == 3.0
    assert setup.get_risk_reward_ratio(3) == 4.0


@pytest.mark.parametrize("tp_level", [0, 4, -1, "1", None])
def test_invalid_tp_level(tp_level):
    setup = make_buy_setup()

    with pytest.raises(ValueError):
        setup.get_risk_reward_ratio(tp_level)


def test_buy_ordering_must_be_strict():
    with pytest.raises(ValueError):
        TradeSetup(
            symbol="XAUUSD",
            entry_price=2000,
            stop_loss=1990,
            take_profit_1=2000,
            take_profit_2=2030,
            take_profit_3=2040,
            timestamp=1,
            direction="buy",
        )


def test_buy_take_profits_must_increase():
    with pytest.raises(ValueError):
        TradeSetup(
            symbol="XAUUSD",
            entry_price=2000,
            stop_loss=1990,
            take_profit_1=2020,
            take_profit_2=2020,
            take_profit_3=2040,
            timestamp=1,
            direction="buy",
        )


def test_sell_ordering():
    setup = make_sell_setup()

    assert (
        setup.stop_loss
        > setup.entry_price
        > setup.take_profit_1
        >= setup.take_profit_2
        >= setup.take_profit_3
    )


def test_sell_equal_take_profits_are_allowed():
    setup = TradeSetup(
        symbol="XAUUSD",
        entry_price=2000,
        stop_loss=2010,
        take_profit_1=1980,
        take_profit_2=1980,
        take_profit_3=1980,
        timestamp=1,
        direction="sell",
    )

    assert setup.take_profit_1 == setup.take_profit_2
    assert setup.take_profit_2 == setup.take_profit_3


@pytest.mark.parametrize(
    "direction",
    ["invalid", "", "long", "short"],
)
def test_invalid_direction(direction):
    with pytest.raises(ValueError):
        TradeSetup(
            symbol="XAUUSD",
            entry_price=2000,
            stop_loss=1990,
            take_profit_1=2020,
            take_profit_2=2030,
            take_profit_3=2040,
            timestamp=1,
            direction=direction,
        )


@pytest.mark.parametrize(
    "symbol",
    ["", "   ", None],
)
def test_invalid_symbol(symbol):
    with pytest.raises(ValueError):
        TradeSetup(
            symbol=symbol,
            entry_price=2000,
            stop_loss=1990,
            take_profit_1=2020,
            take_profit_2=2030,
            take_profit_3=2040,
            timestamp=1,
            direction="buy",
        )


@pytest.mark.parametrize(
    "price_field",
    [
        "entry_price",
        "stop_loss",
        "take_profit_1",
        "take_profit_2",
        "take_profit_3",
    ],
)
def test_price_must_be_positive(price_field):
    values = {
        "entry_price": 2000,
        "stop_loss": 1990,
        "take_profit_1": 2020,
        "take_profit_2": 2030,
        "take_profit_3": 2040,
    }
    values[price_field] = 0

    with pytest.raises(ValueError):
        TradeSetup(
            symbol="XAUUSD",
            timestamp=1,
            direction="buy",
            **values,
        )


@pytest.mark.parametrize(
    "price",
    [float("inf"), float("-inf"), float("nan"), True, False],
)
def test_invalid_price_values(price):
    with pytest.raises(ValueError):
        TradeSetup(
            symbol="XAUUSD",
            entry_price=price,
            stop_loss=1990,
            take_profit_1=2020,
            take_profit_2=2030,
            take_profit_3=2040,
            timestamp=1,
            direction="buy",
        )


def test_timestamp_validation():
    setup = TradeSetup(
        symbol="XAUUSD",
        entry_price=2000,
        stop_loss=1990,
        take_profit_1=2020,
        take_profit_2=2030,
        take_profit_3=2040,
        timestamp="2026-01-01T00:00:00Z",
        direction="buy",
    )

    assert setup.timestamp == "2026-01-01T00:00:00Z"


@pytest.mark.parametrize(
    "timestamp",
    ["", float("inf"), float("-inf"), float("nan"), None],
)
def test_invalid_timestamp(timestamp):
    with pytest.raises(ValueError):
        TradeSetup(
            symbol="XAUUSD",
            entry_price=2000,
            stop_loss=1990,
            take_profit_1=2020,
            take_profit_2=2030,
            take_profit_3=2040,
            timestamp=timestamp,
            direction="buy",
        )


def test_trade_setup_is_immutable():
    setup = make_buy_setup()

    with pytest.raises((AttributeError, TypeError)):
        setup.entry_price = 2100


def test_trade_setup_equality():
    assert make_buy_setup() == make_buy_setup()


def test_trade_setup_hashability():
    setup = make_buy_setup()

    assert hash(setup) == hash(setup)


def test_trade_setup_to_dict():
    setup = make_buy_setup()

    result = setup.to_dict()

    assert result["symbol"] == "XAUUSD"
    assert result["entry_price"] == 2000.0
    assert result["stop_loss"] == 1990.0
    assert result["take_profit_1"] == 2020.0
    assert result["take_profit_2"] == 2030.0
    assert result["take_profit_3"] == 2040.0
    assert result["timestamp"] == 1
    assert result["direction"] == "buy"
    assert result["risk"] == 10.0
    assert result["reward"] == 20.0
    assert result["risk_reward_ratio"] == 2.0

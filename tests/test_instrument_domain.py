import dataclasses

import pytest

from src.platform.domain.instrument import Instrument, VALID_ASSET_CLASSES


def test_valid_instrument():
    instrument = Instrument(symbol="XAUUSD", display_name="Gold vs US Dollar", asset_class="metal")
    assert instrument.symbol == "XAUUSD"
    assert instrument.display_name == "Gold vs US Dollar"
    assert instrument.asset_class == "metal"


def test_defaults():
    instrument = Instrument(symbol="EURUSD")
    assert instrument.display_name is None
    assert instrument.asset_class == "unknown"


def test_asset_class_normalized():
    instrument = Instrument(symbol="BTCUSD", asset_class=" CRYPTO ")
    assert instrument.asset_class == "crypto"


@pytest.mark.parametrize("asset_class", list(VALID_ASSET_CLASSES))
def test_valid_asset_classes(asset_class):
    instrument = Instrument(symbol="SYM", asset_class=asset_class)
    assert instrument.asset_class == asset_class


@pytest.mark.parametrize("symbol", ["", "   ", None, 1])
def test_invalid_symbol_raises(symbol):
    with pytest.raises(ValueError):
        Instrument(symbol=symbol)  # type: ignore[arg-type]


def test_blank_display_name_raises():
    with pytest.raises(ValueError):
        Instrument(symbol="EURUSD", display_name="  ")


def test_invalid_asset_class_raises():
    with pytest.raises(ValueError):
        Instrument(symbol="EURUSD", asset_class="option")


def test_immutability():
    instrument = Instrument(symbol="EURUSD")
    with pytest.raises(dataclasses.FrozenInstanceError):
        instrument.symbol = "XAUUSD"


def test_to_dict():
    instrument = Instrument(symbol="EURUSD", display_name="Euro vs US Dollar", asset_class="forex")
    assert instrument.to_dict() == {
        "symbol": "EURUSD",
        "display_name": "Euro vs US Dollar",
        "asset_class": "forex",
    }

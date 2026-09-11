import pytest

from src.platform.integrations import LabArtifactSource, UnavailableLabArtifactSource


def test_lab_artifact_source_is_abstract():
    assert LabArtifactSource is not None
    with pytest.raises(TypeError):
        LabArtifactSource()  # type: ignore


def test_unavailable_source_returns_none_without_fabrication():
    source = UnavailableLabArtifactSource()
    source.connect()
    assert source.fetch_signal("XAUUSD", "1h") is None
    assert source.fetch_trade_setup("XAUUSD", "1h") is None
    assert source.fetch_stability("momentum") is None
    desc = source.describe()
    assert desc["available"] is False
    assert desc["mode"] == "read-only"
    source.close()


@pytest.mark.parametrize("symbol", ["", "   ", None, 1])
def test_unavailable_source_rejects_invalid_symbol(symbol):
    source = UnavailableLabArtifactSource()
    with pytest.raises(ValueError):
        source.fetch_signal(symbol, "1h")  # type: ignore[arg-type]


@pytest.mark.parametrize("timeframe", ["", "   ", None, 1])
def test_unavailable_source_rejects_invalid_timeframe(timeframe):
    source = UnavailableLabArtifactSource()
    with pytest.raises(ValueError):
        source.fetch_trade_setup("XAUUSD", timeframe)  # type: ignore[arg-type]


def test_unavailable_source_rejects_invalid_strategy_name():
    source = UnavailableLabArtifactSource()
    with pytest.raises(ValueError):
        source.fetch_stability("  ")


def test_unavailable_source_implements_port():
    assert isinstance(UnavailableLabArtifactSource(), LabArtifactSource)

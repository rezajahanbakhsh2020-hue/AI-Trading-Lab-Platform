"""Tests for Walk-Forward domain models."""

import pytest
from src.platform.domain.stability import Stability
from src.platform.domain.walk_forward import WalkForwardResult, WalkForwardWindow


def test_walk_forward_window_valid():
    w = WalkForwardWindow(
        window_index=0,
        in_sample_trades=50,
        in_sample_win_rate=0.65,
        in_sample_profit_factor=2.1,
        out_of_sample_trades=20,
        out_of_sample_win_rate=0.60,
        out_of_sample_profit_factor=1.9,
        out_of_sample_max_drawdown=0.08,
        out_of_sample_net_profit=2500.0,
        efficiency_ratio=0.92,
    )
    assert w.window_index == 0
    assert w.in_sample_trades == 50
    assert w.out_of_sample_win_rate == 0.60
    assert w.to_dict()["efficiency_ratio"] == 0.92


def test_walk_forward_window_invalid():
    with pytest.raises(ValueError, match="window_index must be non-negative"):
        WalkForwardWindow(
            window_index=-1,
            in_sample_trades=50,
            in_sample_win_rate=0.65,
            in_sample_profit_factor=2.1,
            out_of_sample_trades=20,
            out_of_sample_win_rate=0.60,
            out_of_sample_profit_factor=1.9,
            out_of_sample_max_drawdown=0.08,
            out_of_sample_net_profit=2500.0,
            efficiency_ratio=0.92,
        )

    with pytest.raises(ValueError, match="in_sample_win_rate must be between 0.0 and 1.0"):
        WalkForwardWindow(
            window_index=0,
            in_sample_trades=50,
            in_sample_win_rate=1.5,
            in_sample_profit_factor=2.1,
            out_of_sample_trades=20,
            out_of_sample_win_rate=0.60,
            out_of_sample_profit_factor=1.9,
            out_of_sample_max_drawdown=0.08,
            out_of_sample_net_profit=2500.0,
            efficiency_ratio=0.92,
        )


def test_walk_forward_result_valid():
    w1 = WalkForwardWindow(
        window_index=0,
        in_sample_trades=50,
        in_sample_win_rate=0.65,
        in_sample_profit_factor=2.1,
        out_of_sample_trades=20,
        out_of_sample_win_rate=0.60,
        out_of_sample_profit_factor=1.9,
        out_of_sample_max_drawdown=0.08,
        out_of_sample_net_profit=2500.0,
        efficiency_ratio=0.92,
    )
    stab = Stability(score=0.85, risk_level="low")
    res = WalkForwardResult(
        strategy_name="GoldTrendv1",
        symbol="XAUUSD",
        timeframe="1h",
        windows=(w1,),
        overall_out_of_sample_win_rate=0.60,
        overall_out_of_sample_profit_factor=1.9,
        overall_out_of_sample_max_drawdown=0.08,
        overall_out_of_sample_net_profit=2500.0,
        stability=stab,
        detail="Walk-forward validation complete.",
    )
    d = res.to_dict()
    assert d["strategy_name"] == "GoldTrendv1"
    assert len(d["windows"]) == 1
    assert d["stability"]["score"] == 0.85

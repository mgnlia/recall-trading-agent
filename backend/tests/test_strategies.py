"""Tests for trading strategies — basic smoke tests."""

from strategies.mean_reversion import MeanReversionStrategy
from strategies.momentum import MomentumStrategy, Signal


def test_momentum_hold_on_insufficient_data():
    strat = MomentumStrategy()
    sig = strat.evaluate("0xToken")
    assert sig.action == "hold"


def test_momentum_feed_and_evaluate():
    strat = MomentumStrategy(window_short=3, threshold=0.02)
    for p in [100, 101, 102, 103, 106]:
        strat.feed_price("0xToken", p)
    sig = strat.evaluate("0xToken")
    assert isinstance(sig, Signal)
    assert sig.action in ("buy", "sell", "hold")


def test_mean_reversion_hold_on_insufficient_data():
    strat = MeanReversionStrategy()
    sig = strat.evaluate("0xToken")
    assert sig.action == "hold"


def test_mean_reversion_buy_on_dip():
    strat = MeanReversionStrategy(window=5, z_threshold=1.0)
    for p in [100, 100, 100, 100, 100, 100, 100, 100, 100, 80]:
        strat.feed_price("0xToken", p)
    sig = strat.evaluate("0xToken")
    assert sig.action == "buy"

"""Tests for trading strategies."""
import pytest
from app.recall_client import TOKENS
from app.strategy.momentum import MomentumStrategy
from app.strategy.mean_revert import MeanReversionStrategy
from app.strategy.base import Signal

USDC = TOKENS["USDC"]
WETH = TOKENS["WETH"]
WBTC = TOKENS["WBTC"]

@pytest.mark.asyncio
async def test_momentum_buy_signal():
    strat = MomentumStrategy()
    # Simulate 5 samples with strong uptrend (+5%)
    prices = {WETH: [1000, 1010, 1020, 1030, 1050]}
    sig = await strat.generate_signal(prices, 10000, {"USDC": 5000})
    assert sig is not None
    assert sig.signal == Signal.BUY
    assert sig.to_symbol == "WETH"

@pytest.mark.asyncio
async def test_momentum_sell_signal():
    strat = MomentumStrategy()
    # Downtrend
    prices = {WETH: [1050, 1030, 1020, 1010, 1000]}
    sig = await strat.generate_signal(prices, 10000, {"USDC": 100, "WETH": 5000})
    assert sig is not None
    assert sig.signal == Signal.SELL

@pytest.mark.asyncio
async def test_momentum_hold_flat():
    strat = MomentumStrategy()
    prices = {WETH: [1000, 1001, 1000, 1001, 1000]}
    sig = await strat.generate_signal(prices, 10000, {"USDC": 5000})
    assert sig is None  # no signal on flat market

@pytest.mark.asyncio
async def test_mean_revert_buy_oversold():
    strat = MeanReversionStrategy()
    # 10 prices with last price very low (oversold)
    prices = {WETH: [1000]*9 + [900]}  # last price 10% below mean
    sig = await strat.generate_signal(prices, 10000, {"USDC": 5000})
    assert sig is not None
    assert sig.signal == Signal.BUY

@pytest.mark.asyncio
async def test_mean_revert_sell_overbought():
    strat = MeanReversionStrategy()
    prices = {WETH: [1000]*9 + [1100]}  # last price 10% above mean
    sig = await strat.generate_signal(prices, 10000, {"USDC": 100, "WETH": 5000})
    assert sig is not None
    assert sig.signal == Signal.SELL

@pytest.mark.asyncio
async def test_insufficient_history_returns_none():
    strat = MomentumStrategy()
    prices = {WETH: [1000, 1010]}  # only 2 samples, need 5
    sig = await strat.generate_signal(prices, 10000, {"USDC": 5000})
    assert sig is None

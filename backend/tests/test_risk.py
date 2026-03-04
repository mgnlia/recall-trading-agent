"""Tests for RiskManager."""
import pytest
from app.risk import RiskManager
from app.config import settings

def test_initial_state():
    rm = RiskManager()
    assert not rm.is_halted
    assert rm.state.peak_value == 0.0

def test_peak_tracking():
    rm = RiskManager()
    rm.update_portfolio_value(10000)
    assert rm.state.peak_value == 10000
    rm.update_portfolio_value(12000)
    assert rm.state.peak_value == 12000
    rm.update_portfolio_value(11000)
    assert rm.state.peak_value == 12000  # peak stays

def test_drawdown_halt():
    rm = RiskManager()
    rm.update_portfolio_value(10000)
    # Drop 15% — should trigger halt (threshold is 10%)
    rm.update_portfolio_value(8500)
    assert rm.is_halted
    assert "drawdown" in rm.state.halt_reason.lower()

def test_no_halt_within_limit():
    rm = RiskManager()
    rm.update_portfolio_value(10000)
    rm.update_portfolio_value(9100)  # 9% drop — within limit
    assert not rm.is_halted

def test_size_trade():
    rm = RiskManager()
    rm.update_portfolio_value(10000)
    size = rm.size_trade(10000, 5000, 1.0)
    assert size > 0
    assert size <= 10000 * settings.max_trade_pct

def test_size_trade_halted():
    rm = RiskManager()
    rm.halt("test")
    size = rm.size_trade(10000, 5000, 1.0)
    assert size == 0

def test_position_limit():
    rm = RiskManager()
    rm.update_portfolio_value(10000)
    # Trying to buy $3000 more when already holding $0 → 30% > 25% limit
    allowed, reason = rm.check_position(10000, 0, 3000)
    assert not allowed

def test_position_allowed():
    rm = RiskManager()
    rm.update_portfolio_value(10000)
    allowed, reason = rm.check_position(10000, 0, 2000)  # 20% < 25%
    assert allowed

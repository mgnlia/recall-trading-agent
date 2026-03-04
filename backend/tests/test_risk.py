"""Tests for RiskManager."""

from risk import RiskManager


def test_initial_state():
    rm = RiskManager()
    assert rm.halted is False
    assert rm.peak_portfolio_value == 0.0


def test_position_size_limit():
    rm = RiskManager()
    assert rm.check_position_size(2500, 10000) is True
    assert rm.check_position_size(2501, 10000) is False


def test_drawdown_halt():
    rm = RiskManager()
    rm.update_portfolio_value(10000)
    assert rm.halted is False
    rm.update_portfolio_value(8400)  # 16% drawdown exceeds 15% limit
    assert rm.halted is True


def test_optimal_trade_size():
    rm = RiskManager()
    size = rm.optimal_trade_size(10000, 0.5)
    assert 0 < size <= 2500

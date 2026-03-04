"""Tests for RiskManager."""

from risk import RiskManager


def test_initial_state():
    rm = RiskManager()
    assert rm.halted is False
    assert rm.peak_value == 0.0


def test_position_size_limit():
    rm = RiskManager(max_position_pct=0.25)
    assert rm.check_position_size(2500, 10000) is True
    assert rm.check_position_size(2501, 10000) is False


def test_drawdown_halt():
    rm = RiskManager(max_drawdown_pct=0.10)
    rm.update_portfolio_value(10000)
    assert rm.halted is False
    rm.update_portfolio_value(8900)  # 11% drawdown
    assert rm.halted is True


def test_optimal_trade_size():
    rm = RiskManager(max_position_pct=0.25)
    size = rm.optimal_trade_size(10000, 0.5)
    assert 0 < size <= 2500

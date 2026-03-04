"""Risk management — position limits, drawdown checks, trade sizing."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class RiskManager:
    """Enforces position limits and max-drawdown circuit breaker."""

    peak_portfolio_value: float = 0.0
    current_drawdown: float = 0.0
    halted: bool = False
    _trade_log: list[dict[str, Any]] = field(default_factory=list)

    # --- public API -----------------------------------------------------------

    def update_portfolio_value(self, value: float) -> None:
        """Track peak value and current drawdown."""
        if value > self.peak_portfolio_value:
            self.peak_portfolio_value = value
        if self.peak_portfolio_value > 0:
            self.current_drawdown = 1.0 - (value / self.peak_portfolio_value)
        if self.current_drawdown >= settings.max_drawdown_pct:
            self.halted = True
            logger.warning(
                "Risk halt triggered — drawdown %.2f%% exceeds limit %.2f%%",
                self.current_drawdown * 100,
                settings.max_drawdown_pct * 100,
            )

    def check_position_size(
        self, trade_value_usd: float, portfolio_value: float
    ) -> bool:
        """Return True if the proposed trade is within position limits."""
        if self.halted:
            logger.warning("Trading halted due to drawdown limit.")
            return False
        if portfolio_value <= 0:
            return False
        position_pct = trade_value_usd / portfolio_value
        if position_pct > settings.max_position_pct:
            logger.info(
                "Trade rejected — %.1f%% exceeds max position %.1f%%",
                position_pct * 100,
                settings.max_position_pct * 100,
            )
            return False
        return True

    def optimal_trade_size(self, portfolio_value: float, confidence: float) -> float:
        """Kelly-inspired sizing: scale trade by confidence within limits."""
        max_trade = portfolio_value * settings.max_position_pct
        return max_trade * min(max(confidence, 0.0), 1.0)

    def record_trade(self, trade: dict[str, Any]) -> None:
        self._trade_log.append(trade)

    @property
    def trade_history(self) -> list[dict[str, Any]]:
        return list(self._trade_log)

    def reset(self) -> None:
        self.peak_portfolio_value = 0.0
        self.current_drawdown = 0.0
        self.halted = False
        self._trade_log.clear()

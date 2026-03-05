"""Recall airdrop score optimizer.

Maximizes the RECALL airdrop score by encouraging:
- Trade frequency (active participation)
- Portfolio diversification across chains
- Consistent performance (Sharpe ratio)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date

from strategies.momentum import Signal

logger = logging.getLogger(__name__)


@dataclass
class AirdropMetrics:
    """Tracks metrics relevant to RECALL airdrop scoring."""

    total_trades: int = 0
    trades_today: int = 0
    unique_tokens_traded: set[str] = field(default_factory=set)
    chains_used: set[str] = field(default_factory=set)
    last_trade_ts: float = 0.0
    daily_returns: list[float] = field(default_factory=list)
    # Track the last date we reset trades_today so it resets at midnight
    _last_reset_date: date = field(default_factory=date.today)

    def maybe_reset_daily(self) -> None:
        """Reset trades_today if the calendar day has rolled over."""
        today = date.today()
        if today != self._last_reset_date:
            logger.info(
                "Daily reset: trades_today %d → 0 (was %s, now %s)",
                self.trades_today,
                self._last_reset_date,
                today,
            )
            self.trades_today = 0
            self._last_reset_date = today

    @property
    def activity_score(self) -> float:
        """0-1 score based on trading activity."""
        freq_score = min(self.trades_today / 10.0, 1.0)
        diversity_score = min(len(self.unique_tokens_traded) / 5.0, 1.0)
        chain_score = min(len(self.chains_used) / 3.0, 1.0)
        return freq_score * 0.4 + diversity_score * 0.35 + chain_score * 0.25

    @property
    def estimated_airdrop_score(self) -> float:
        """Rough estimate of airdrop points (0-100 scale)."""
        return self.activity_score * 100.0


@dataclass
class RecallOptimizer:
    """Generates signals to optimize airdrop score when other strategies are idle."""

    min_trade_gap_seconds: float = 300.0  # don't spam trades
    metrics: AirdropMetrics = field(default_factory=AirdropMetrics)
    _diversification_targets: list[str] = field(default_factory=list)

    def set_diversification_targets(self, tokens: list[str]) -> None:
        self._diversification_targets = tokens

    def record_trade(self, token: str, chain: str = "evm") -> None:
        # Always check for day rollover before incrementing
        self.metrics.maybe_reset_daily()
        self.metrics.total_trades += 1
        self.metrics.trades_today += 1
        self.metrics.unique_tokens_traded.add(token)
        self.metrics.chains_used.add(chain)
        self.metrics.last_trade_ts = time.time()

    def evaluate(self, portfolio_tokens: list[str]) -> Signal:
        """Suggest a trade to boost airdrop score if activity is low."""
        # Always check for day rollover before reading trades_today
        self.metrics.maybe_reset_daily()

        now = time.time()
        gap = now - self.metrics.last_trade_ts

        if gap < self.min_trade_gap_seconds:
            return Signal("hold", "", 0.0, "Too soon since last trade for airdrop optimization")

        # Find a token we haven't traded yet for diversity
        untouched = [
            t for t in self._diversification_targets
            if t not in self.metrics.unique_tokens_traded
        ]
        if untouched:
            target = untouched[0]
            return Signal(
                "buy",
                target,
                0.3,
                f"Airdrop optimizer: diversify into {target[:10]}... for score boost",
            )

        # Encourage at least 3 trades per day for activity score
        if self.metrics.trades_today < 3:
            target = self._diversification_targets[0] if self._diversification_targets else ""
            if target:
                return Signal(
                    "buy",
                    target,
                    0.2,
                    f"Airdrop optimizer: maintain daily activity ({self.metrics.trades_today}/3 today)",
                )

        return Signal("hold", "", 0.0, "Airdrop activity sufficient for today")

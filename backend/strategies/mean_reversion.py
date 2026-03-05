"""Mean-reversion trading strategy."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

from strategies.momentum import Signal

logger = logging.getLogger(__name__)


@dataclass
class MeanReversionStrategy:
    """Z-score mean reversion strategy."""

    window: int = 20
    z_threshold: float = 1.5
    _prices: dict[str, list[float]] = field(default_factory=dict)

    def feed_price(self, token: str, price: float) -> None:
        self._prices.setdefault(token, [])
        self._prices[token].append(price)
        max_len = self.window * 3
        if len(self._prices[token]) > max_len:
            self._prices[token] = self._prices[token][-max_len:]

    def evaluate(self, token: str) -> Signal:
        prices = self._prices.get(token, [])
        if len(prices) < self.window:
            return Signal("hold", token, 0.0, "Insufficient data for mean reversion")

        window_prices = prices[-self.window:]
        mean = sum(window_prices) / len(window_prices)
        variance = sum((p - mean) ** 2 for p in window_prices) / len(window_prices)
        std = math.sqrt(variance) if variance > 0 else 0.0001

        current = prices[-1]
        z_score = (current - mean) / std
        confidence = min(abs(z_score) / (self.z_threshold * 2), 1.0)

        if z_score < -self.z_threshold:
            return Signal(
                "buy",
                token,
                confidence,
                f"Mean reversion BUY: z={z_score:.2f}, price={current:.2f}, mean={mean:.2f}",
            )
        elif z_score > self.z_threshold:
            return Signal(
                "sell",
                token,
                confidence,
                f"Mean reversion SELL: z={z_score:.2f}, price={current:.2f}, mean={mean:.2f}",
            )
        return Signal("hold", token, 0.0, f"No mean reversion signal: z={z_score:.2f}")

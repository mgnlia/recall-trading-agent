"""Momentum-based trading strategy.

Tracks recent price changes and generates buy signals when short-term
momentum exceeds a threshold, sell signals when momentum reverses.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    """A trading signal produced by a strategy."""
    action: str  # "buy" | "sell" | "hold"
    token: str
    confidence: float  # 0.0 – 1.0
    reason: str


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------

@dataclass
class MomentumStrategy:
    """Simple price-momentum strategy.

    Keeps a rolling window of prices per token and fires when the
    short-window return exceeds *threshold*.
    """

    window_short: int = 5
    window_long: int = 20
    threshold: float = 0.02  # 2 % move
    _prices: dict[str, list[float]] = field(default_factory=dict)

    def feed_price(self, token: str, price: float) -> None:
        """Append a new price observation."""
        self._prices.setdefault(token, [])
        self._prices[token].append(price)
        # keep at most window_long * 2 entries
        max_len = self.window_long * 2
        if len(self._prices[token]) > max_len:
            self._prices[token] = self._prices[token][-max_len:]

    def evaluate(self, token: str) -> Signal:
        """Return a Signal for *token* based on recent momentum."""
        prices = self._prices.get(token, [])
        if len(prices) < self.window_short + 1:
            return Signal("hold", token, 0.0, "Insufficient price data for momentum")

        short_slice = prices[-self.window_short:]
        short_return = (short_slice[-1] - short_slice[0]) / short_slice[0]

        long_return = 0.0
        if len(prices) >= self.window_long + 1:
            long_slice = prices[-self.window_long:]
            long_return = (long_slice[-1] - long_slice[0]) / long_slice[0]

        confidence = min(abs(short_return) / (self.threshold * 2), 1.0)

        if short_return > self.threshold and short_return > long_return:
            return Signal(
                "buy",
                token,
                confidence,
                f"Momentum UP: short={short_return:+.2%} long={long_return:+.2%}",
            )
        elif short_return < -self.threshold:
            return Signal(
                "sell",
                token,
                confidence,
                f"Momentum DOWN: short={short_return:+.2%} long={long_return:+.2%}",
            )
        return Signal("hold", token, 0.0, f"No momentum signal: short={short_return:+.2%}")

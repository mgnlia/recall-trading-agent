"""Sentiment-based trading strategy.

Produces BUY/SELL/HOLD signals from three price-derived sub-signals:
  1. Short-term vs long-term momentum divergence  (40% weight)
  2. Volatility regime                            (30% weight)
  3. Synthetic headline keyword scoring           (30% weight)

No external API is required — all signals are derived from price history.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field

from strategies.momentum import Signal

logger = logging.getLogger(__name__)

# Simulated headline templates weighted by market regime
_BULLISH_HEADLINES = [
    "Bitcoin surges past key resistance as institutional demand rises",
    "Crypto market cap hits new high amid ETF inflows",
    "DeFi TVL surges as altcoin season begins",
    "ETH upgrade boosts confidence; analysts target new highs",
]
_BEARISH_HEADLINES = [
    "Crypto selloff deepens on macro uncertainty",
    "Whales move BTC to exchanges signalling distribution",
    "Regulatory crackdown fears weigh on crypto markets",
    "Risk-off sentiment spreads as DXY strengthens",
]
_NEUTRAL_HEADLINES = [
    "Crypto markets consolidate after recent moves",
    "Bitcoin trades sideways as traders await catalyst",
    "Mixed signals from on-chain data; analysts divided",
]

_BULLISH_KEYWORDS = {"surge", "rises", "high", "inflows", "upgrade", "boosts", "target"}
_BEARISH_KEYWORDS = {"selloff", "deepens", "uncertainty", "distribution", "crackdown", "fears", "risk-off"}


def _score_headline(headline: str) -> float:
    """Return sentiment score in [-1, +1] from keyword matching."""
    words = set(headline.lower().split())
    bull = len(words & _BULLISH_KEYWORDS)
    bear = len(words & _BEARISH_KEYWORDS)
    total = bull + bear
    if total == 0:
        return 0.0
    return (bull - bear) / total


@dataclass
class SentimentStrategy:
    """Synthetic sentiment strategy — no external API required.

    Internal weights:
      momentum_divergence : 40%
      volatility_regime   : 30%
      headline_sentiment  : 30%
    """

    window_short: int = 5
    window_long: int = 20
    vol_window: int = 14
    threshold: float = 0.55
    _prices: dict[str, list[float]] = field(default_factory=dict)
    _rng: random.Random = field(default_factory=lambda: random.Random(42))

    def feed_price(self, token: str, price: float) -> None:
        self._prices.setdefault(token, [])
        self._prices[token].append(price)
        max_len = self.window_long * 3
        if len(self._prices[token]) > max_len:
            self._prices[token] = self._prices[token][-max_len:]
        self._rng = random.Random(int(price * 1000) % (2**32))

    def evaluate(self, token: str) -> Signal:
        prices = self._prices.get(token, [])
        if len(prices) < self.window_long + 1:
            return Signal("hold", token, 0.0, "Insufficient data for sentiment analysis")

        # --- 1. Momentum divergence (40%) ---
        short_slice = prices[-self.window_short:]
        long_slice = prices[-self.window_long:]
        short_ret = (short_slice[-1] - short_slice[0]) / short_slice[0]
        long_ret = (long_slice[-1] - long_slice[0]) / long_slice[0]
        divergence = short_ret - long_ret
        div_score = max(-1.0, min(1.0, divergence / 0.05))

        # --- 2. Volatility regime (30%) ---
        returns = [
            (prices[i] - prices[i - 1]) / prices[i - 1]
            for i in range(max(1, len(prices) - self.vol_window), len(prices))
        ]
        if returns:
            mean_r = sum(returns) / len(returns)
            vol = math.sqrt(sum((r - mean_r) ** 2 for r in returns) / len(returns))
        else:
            vol = 0.0
        vol_threshold = 0.02
        if vol > vol_threshold:
            vol_score = -math.copysign(min(vol / vol_threshold, 1.0), short_ret)
        else:
            vol_score = math.copysign(min(abs(short_ret) / 0.01, 1.0), short_ret)

        # --- 3. Headline keyword scoring (30%) ---
        if short_ret > 0.01:
            pool = _BULLISH_HEADLINES + _NEUTRAL_HEADLINES
        elif short_ret < -0.01:
            pool = _BEARISH_HEADLINES + _NEUTRAL_HEADLINES
        else:
            pool = _NEUTRAL_HEADLINES + _BULLISH_HEADLINES + _BEARISH_HEADLINES
        headline = self._rng.choice(pool)
        headline_score = _score_headline(headline)

        # --- Weighted composite ---
        composite = (
            0.40 * div_score
            + 0.30 * vol_score
            + 0.30 * headline_score
        )
        confidence = min(abs(composite), 1.0)

        logger.debug(
            "Sentiment[%s]: div=%.3f vol=%.3f headline=%.3f → composite=%.3f",
            token[:10], div_score, vol_score, headline_score, composite,
        )

        if composite > self.threshold:
            return Signal(
                "buy", token, confidence,
                f"Sentiment BUY: score={composite:.3f} headline='{headline[:50]}...'",
            )
        elif composite < -self.threshold:
            return Signal(
                "sell", token, confidence,
                f"Sentiment SELL: score={composite:.3f} headline='{headline[:50]}...'",
            )
        return Signal("hold", token, 0.0, f"Sentiment neutral: score={composite:.3f}")

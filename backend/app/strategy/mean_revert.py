"""
Mean Reversion Strategy.

Logic:
- Compute rolling mean and standard deviation over a window.
- Calculate z-score: (current_price - mean) / std.
- If z-score < -threshold → price is unusually low → BUY (expect rebound).
- If z-score > +threshold → price is unusually high → SELL (expect pullback).
- Signal strength = normalized z-score magnitude.

Works best in range-bound, choppy markets.
"""
import math
import structlog
from typing import Optional

from app.config import settings
from app.recall_client import TOKENS
from app.strategy.base import BaseStrategy, Signal, TradeSignal

logger = structlog.get_logger(__name__)

USDC_ADDR = TOKENS["USDC"]
USDC_SYMBOL = "USDC"

# Tokens eligible for mean reversion (prefer liquid, less volatile)
MR_UNIVERSE = [
    ("WETH", TOKENS["WETH"]),
    ("WBTC", TOKENS["WBTC"]),
    ("LINK", TOKENS["LINK"]),
    ("AAVE", TOKENS["AAVE"]),
]


def _zscore(prices: list[float]) -> float:
    """Compute z-score of the last price vs. the window."""
    if len(prices) < 3:
        return 0.0
    n = len(prices)
    mean = sum(prices) / n
    variance = sum((p - mean) ** 2 for p in prices) / n
    std = math.sqrt(variance) if variance > 0 else 0.0
    if std == 0:
        return 0.0
    return (prices[-1] - mean) / std


class MeanReversionStrategy(BaseStrategy):
    """
    Z-score mean reversion strategy.
    Buys dips, sells rips, relative to recent price history.
    """

    name = "mean_reversion"

    async def generate_signal(
        self,
        price_history: dict[str, list[float]],
        portfolio_value: float,
        token_balances: dict[str, float],
    ) -> Optional[TradeSignal]:
        window = settings.mean_revert_window
        z_thresh = settings.mean_revert_z_threshold

        best_signal: Optional[TradeSignal] = None
        best_strength = 0.0

        for symbol, addr in MR_UNIVERSE:
            prices = price_history.get(addr, [])
            if len(prices) < window:
                continue

            recent = prices[-window:]
            z = _zscore(recent)

            # Oversold → BUY
            if z < -z_thresh:
                strength = min(abs(z) / (z_thresh * 2), 1.0)
                usdc_balance = token_balances.get("USDC", 0)

                if usdc_balance > settings.min_trade_usd:
                    sig = TradeSignal(
                        signal=Signal.BUY,
                        from_token=USDC_ADDR,
                        to_token=addr,
                        from_symbol=USDC_SYMBOL,
                        to_symbol=symbol,
                        strength=strength,
                        reason=f"Mean reversion: z={z:.2f} (oversold), expect rebound",
                        strategy_name=self.name,
                    )
                    if strength > best_strength:
                        best_strength = strength
                        best_signal = sig
                        logger.debug(
                            "mean_revert.buy_signal",
                            symbol=symbol,
                            z_score=round(z, 3),
                            strength=strength,
                        )

            # Overbought → SELL
            elif z > z_thresh:
                strength = min(abs(z) / (z_thresh * 2), 1.0)
                token_balance = token_balances.get(symbol, 0)

                if token_balance > settings.min_trade_usd:
                    sig = TradeSignal(
                        signal=Signal.SELL,
                        from_token=addr,
                        to_token=USDC_ADDR,
                        from_symbol=symbol,
                        to_symbol=USDC_SYMBOL,
                        strength=strength,
                        reason=f"Mean reversion: z={z:.2f} (overbought), expect pullback",
                        strategy_name=self.name,
                    )
                    if strength > best_strength:
                        best_strength = strength
                        best_signal = sig
                        logger.debug(
                            "mean_revert.sell_signal",
                            symbol=symbol,
                            z_score=round(z, 3),
                            strength=strength,
                        )

        return best_signal

"""
Momentum / Trend-Following Strategy.

Logic:
- Compute % price change over a rolling window.
- If price has risen > threshold → BUY (ride the trend).
- If price has fallen > threshold → SELL back to USDC.
- Signal strength = normalized momentum magnitude (capped at 1.0).

Works best in trending markets.
"""
import structlog
from typing import Optional

from app.config import settings
from app.recall_client import TOKENS
from app.strategy.base import BaseStrategy, Signal, TradeSignal

logger = structlog.get_logger(__name__)

USDC_ADDR = TOKENS["USDC"]
USDC_SYMBOL = "USDC"

# Tokens we're willing to buy with momentum
MOMENTUM_UNIVERSE = [
    ("WETH", TOKENS["WETH"]),
    ("WBTC", TOKENS["WBTC"]),
    ("LINK", TOKENS["LINK"]),
    ("UNI",  TOKENS["UNI"]),
]


class MomentumStrategy(BaseStrategy):
    """
    Simple price-momentum strategy.
    Buys assets trending upward, sells to USDC when trend reverses.
    """

    name = "momentum"

    async def generate_signal(
        self,
        price_history: dict[str, list[float]],
        portfolio_value: float,
        token_balances: dict[str, float],
    ) -> Optional[TradeSignal]:
        window = settings.momentum_window
        threshold = settings.momentum_threshold

        best_signal: Optional[TradeSignal] = None
        best_strength = 0.0

        for symbol, addr in MOMENTUM_UNIVERSE:
            prices = price_history.get(addr, [])
            if len(prices) < window:
                continue

            recent = prices[-window:]
            start_price = recent[0]
            end_price = recent[-1]

            if start_price <= 0:
                continue

            momentum = (end_price - start_price) / start_price

            # Strong uptrend → BUY
            if momentum > threshold:
                strength = min(momentum / (threshold * 5), 1.0)
                usdc_balance = token_balances.get("USDC", 0)

                if usdc_balance > settings.min_trade_usd:
                    sig = TradeSignal(
                        signal=Signal.BUY,
                        from_token=USDC_ADDR,
                        to_token=addr,
                        from_symbol=USDC_SYMBOL,
                        to_symbol=symbol,
                        strength=strength,
                        reason=f"Momentum +{momentum:.2%} over {window} samples",
                        strategy_name=self.name,
                    )
                    if strength > best_strength:
                        best_strength = strength
                        best_signal = sig
                        logger.debug(
                            "momentum.buy_signal",
                            symbol=symbol,
                            momentum=f"{momentum:.2%}",
                            strength=strength,
                        )

            # Strong downtrend → SELL (exit to USDC)
            elif momentum < -threshold:
                strength = min(abs(momentum) / (threshold * 5), 1.0)
                token_balance = token_balances.get(symbol, 0)

                if token_balance > settings.min_trade_usd:
                    sig = TradeSignal(
                        signal=Signal.SELL,
                        from_token=addr,
                        to_token=USDC_ADDR,
                        from_symbol=symbol,
                        to_symbol=USDC_SYMBOL,
                        strength=strength,
                        reason=f"Momentum {momentum:.2%} over {window} samples — exit",
                        strategy_name=self.name,
                    )
                    if strength > best_strength:
                        best_strength = strength
                        best_signal = sig
                        logger.debug(
                            "momentum.sell_signal",
                            symbol=symbol,
                            momentum=f"{momentum:.2%}",
                            strength=strength,
                        )

        return best_signal

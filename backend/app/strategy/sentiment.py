"""
Sentiment / News Strategy — lightweight signal from price momentum cross-asset.
In production, wire this to a news API or social feed.
For competition: uses BTC dominance proxy and cross-asset correlation.
"""
import structlog
from typing import Optional
from app.config import settings
from app.recall_client import TOKENS
from app.strategy.base import BaseStrategy, Signal, TradeSignal

logger = structlog.get_logger(__name__)
USDC_ADDR = TOKENS["USDC"]

class SentimentStrategy(BaseStrategy):
    name = "sentiment"
    async def generate_signal(self, price_history, portfolio_value, token_balances):
        # BTC as market sentiment proxy
        btc_prices = price_history.get(TOKENS["WBTC"], [])
        eth_prices = price_history.get(TOKENS["WETH"], [])
        if len(btc_prices) < 3 or len(eth_prices) < 3:
            return None
        btc_mom = (btc_prices[-1] - btc_prices[-3]) / btc_prices[-3] if btc_prices[-3] > 0 else 0
        eth_mom = (eth_prices[-1] - eth_prices[-3]) / eth_prices[-3] if eth_prices[-3] > 0 else 0
        # Both rising = risk-on, buy ETH
        if btc_mom > 0.01 and eth_mom > 0.005:
            usdc_bal = token_balances.get("USDC", 0)
            if usdc_bal > settings.min_trade_usd:
                return TradeSignal(signal=Signal.BUY, from_token=USDC_ADDR, to_token=TOKENS["WETH"],
                    from_symbol="USDC", to_symbol="WETH", strength=min(btc_mom * 20, 0.8),
                    reason=f"Risk-on: BTC+{btc_mom:.2%} ETH+{eth_mom:.2%}", strategy_name=self.name)
        # Both falling = risk-off, sell to USDC
        if btc_mom < -0.01 and eth_mom < -0.005:
            eth_bal = token_balances.get("WETH", 0)
            if eth_bal > settings.min_trade_usd:
                return TradeSignal(signal=Signal.SELL, from_token=TOKENS["WETH"], to_token=USDC_ADDR,
                    from_symbol="WETH", to_symbol="USDC", strength=min(abs(btc_mom) * 20, 0.8),
                    reason=f"Risk-off: BTC{btc_mom:.2%} ETH{eth_mom:.2%}", strategy_name=self.name)
        return None

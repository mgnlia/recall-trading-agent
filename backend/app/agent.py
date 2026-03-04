"""
Main Agent Loop — orchestrates scanner → strategy → risk → trade.

Runs as an async background task. Each iteration:
1. Fetch portfolio
2. Fetch prices for all tracked tokens
3. Run all strategies, collect signals
4. Weight signals by strategy weights
5. Pick best signal, check risk limits, execute trade
6. Broadcast state via SSE
"""
import asyncio
import structlog
from collections import defaultdict, deque
from datetime import datetime
from typing import Optional

from app.config import settings
from app.recall_client import RecallClient, TOKENS, Portfolio
from app.risk import RiskManager
from app.strategy.base import Signal, TradeSignal
from app.strategy.momentum import MomentumStrategy
from app.strategy.mean_revert import MeanReversionStrategy
from app.strategy.sentiment import SentimentStrategy

logger = structlog.get_logger(__name__)

MAX_HISTORY = 50

TRACKED_TOKENS = [
    (TOKENS["WETH"], "evm", "eth"),
    (TOKENS["WBTC"], "evm", "eth"),
    (TOKENS["LINK"], "evm", "eth"),
    (TOKENS["UNI"],  "evm", "eth"),
    (TOKENS["AAVE"], "evm", "eth"),
]

STRATEGY_WEIGHTS = {
    "momentum":       settings.momentum_weight,
    "mean_reversion": settings.mean_revert_weight,
    "sentiment":      settings.sentiment_weight,
}


class TradingAgent:
    def __init__(self):
        self.client = RecallClient()
        self.risk = RiskManager()
        self.strategies = [
            MomentumStrategy(),
            MeanReversionStrategy(),
            SentimentStrategy(),
        ]
        self.price_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))
        self.portfolio: Optional[Portfolio] = None
        self.last_trade: Optional[dict] = None
        self.trade_history: list[dict] = []
        self.running = False
        self.iteration = 0
        self.last_cycle_at: Optional[str] = None
        self.last_error: str = ""
        self.last_signals: dict = {}
        self.sse_subscribers: list[asyncio.Queue] = []

    async def start(self):
        self.running = True
        logger.info("agent.start", sandbox=settings.use_sandbox)
        asyncio.create_task(self._loop())

    async def stop(self):
        self.running = False
        logger.info("agent.stop")

    async def _loop(self):
        while self.running:
            try:
                await self._tick()
            except Exception as e:
                self.last_error = str(e)
                logger.error("agent.loop_error", error=str(e))
            await asyncio.sleep(settings.trade_interval_secs)

    async def _tick(self):
        self.iteration += 1
        self.last_cycle_at = datetime.utcnow().isoformat()
        logger.info("agent.tick", iteration=self.iteration)

        # 1. Refresh portfolio
        if not self.client.has_credentials:
            logger.warning("agent.no_api_key")
            await self._broadcast(self.get_status())
            return

        self.portfolio = await self.client.get_portfolio()
        self.risk.update_portfolio_value(self.portfolio.total_value)

        # 2. Fetch prices
        prices = await self.client.get_prices_batch(TRACKED_TOKENS)
        for addr, price in prices.items():
            if price > 0:
                self.price_history[addr].append(price)

        # Build token_balances dict: symbol -> USD value
        token_balances: dict[str, float] = {}
        for tb in self.portfolio.tokens:
            token_balances[tb.symbol] = tb.value

        # 3. Run strategies, collect signals
        signals: list[tuple[TradeSignal, float]] = []
        price_hist_dict = {addr: list(dq) for addr, dq in self.price_history.items()}
        self.last_signals = {}

        for strategy in self.strategies:
            try:
                sig = await strategy.generate_signal(
                    price_hist_dict,
                    self.portfolio.total_value,
                    token_balances,
                )
                if sig:
                    self.last_signals[f"{strategy.name}:{sig.from_symbol}->{sig.to_symbol}"] = {
                        "signal": sig.signal.value,
                        "strategy": sig.strategy_name,
                        "strength": round(sig.strength, 3),
                        "reason": sig.reason,
                    }
                    if sig.signal != Signal.HOLD:
                        weight = STRATEGY_WEIGHTS.get(strategy.name, 0.33)
                        signals.append((sig, weight))
                        logger.info(
                            "agent.signal",
                            strategy=strategy.name,
                            signal=sig.signal.value,
                            from_sym=sig.from_symbol,
                            to_sym=sig.to_symbol,
                            strength=round(sig.strength, 3),
                        )
            except Exception as e:
                logger.error("agent.strategy_error", strategy=strategy.name, error=str(e))

        # 4. Pick best weighted signal
        best_signal: Optional[TradeSignal] = None
        best_score = 0.0
        for sig, weight in signals:
            score = sig.strength * weight
            if score > best_score:
                best_score = score
                best_signal = sig

        # 5. Execute trade if signal exists and risk allows
        if best_signal and not self.risk.is_halted:
            from_token_value = token_balances.get(best_signal.from_symbol, 0)
            trade_usd = self.risk.size_trade(
                self.portfolio.total_value,
                from_token_value,
                best_signal.strength,
            )

            if trade_usd > 0:
                from_price = next(
                    (tb.price for tb in self.portfolio.tokens if tb.symbol == best_signal.from_symbol),
                    1.0,
                )
                amount_tokens = trade_usd / from_price if from_price > 0 else 0

                allowed, reason = self.risk.check_position(
                    self.portfolio.total_value,
                    token_balances.get(best_signal.to_symbol, 0),
                    trade_usd,
                )

                if allowed and amount_tokens > 0:
                    trade_result = await self.client.execute_trade(
                        from_token=best_signal.from_token,
                        to_token=best_signal.to_token,
                        amount=amount_tokens,
                        from_chain=best_signal.from_chain,
                        to_chain=best_signal.to_chain,
                        from_specific_chain=best_signal.from_specific_chain,
                        to_specific_chain=best_signal.to_specific_chain,
                        reason=f"[{best_signal.strategy_name}] {best_signal.reason}",
                    )
                    if trade_result.success:
                        self.risk.record_trade()
                        record = {
                            "timestamp": trade_result.timestamp or self.last_cycle_at,
                            "tx_id": trade_result.transaction_id,
                            "from_symbol": best_signal.from_symbol,
                            "to_symbol": best_signal.to_symbol,
                            "from_amount": trade_result.from_amount,
                            "to_amount": trade_result.to_amount,
                            "price": trade_result.price,
                            "strategy": best_signal.strategy_name,
                            "reason": best_signal.reason,
                            "amount_usd": round(trade_usd, 2),
                        }
                        self.last_trade = record
                        self.trade_history.append(record)
                        if len(self.trade_history) > 500:
                            self.trade_history = self.trade_history[-500:]
                        logger.info(
                            "agent.trade_executed",
                            from_sym=best_signal.from_symbol,
                            to_sym=best_signal.to_symbol,
                            usd=round(trade_usd, 2),
                            tx=trade_result.transaction_id,
                        )
                else:
                    logger.info("agent.trade_blocked", reason=reason)

        # 6. Broadcast state
        await self._broadcast(self.get_status())

    async def _broadcast(self, data: dict):
        dead = []
        for q in self.sse_subscribers:
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.sse_subscribers.remove(q)

    def get_status(self) -> dict:
        risk = self.risk.to_dict()
        portfolio_value = risk.get("current_value", 0.0)
        if self.portfolio:
            portfolio_value = self.portfolio.total_value

        return {
            # Agent meta
            "running": self.running,
            "iteration": self.iteration,
            "last_cycle_at": self.last_cycle_at,
            "agent_name": settings.agent_name,
            "sandbox": settings.use_sandbox,
            # Portfolio
            "portfolio_value": round(portfolio_value, 2),
            "portfolio_tokens": [
                {"symbol": t.symbol, "amount": t.amount, "price": t.price, "value": round(t.value, 2)}
                for t in (self.portfolio.tokens if self.portfolio else [])
            ],
            # P&L / risk
            "daily_pnl": risk.get("daily_pnl", 0.0),
            "daily_pnl_pct": risk.get("daily_pnl_pct", 0.0),
            "drawdown_pct": risk.get("drawdown_from_peak_pct", 0.0),
            "halted": risk.get("halted", False),
            "halt_reason": risk.get("halt_reason", ""),
            "trade_count_today": risk.get("trade_count_today", 0),
            "total_trades": risk.get("total_trades", 0),
            # Signals
            "last_signals": self.last_signals,
            "last_trade": self.last_trade,
            "last_error": self.last_error,
        }


# Singleton
agent = TradingAgent()

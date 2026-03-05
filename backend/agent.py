"""Main trading agent loop.

Orchestrates strategies, risk management, and Recall API interaction.
Runs as an asyncio background task within the FastAPI app.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from config import settings
from risk import RiskManager
from strategies.mean_reversion import MeanReversionStrategy
from strategies.momentum import MomentumStrategy, Signal
from strategies.recall_optimizer import RecallOptimizer
from strategies.sentiment import SentimentStrategy

logger = logging.getLogger(__name__)

# Strategy weights — must sum to 1.0
STRATEGY_WEIGHTS = {
    "momentum": 0.50,
    "mean_reversion": 0.30,
    "sentiment": 0.20,
}

# Well-known tokens to track
TRACKED_TOKENS = [
    {"address": settings.weth_address, "symbol": "WETH", "chain": "evm", "specificChain": "eth"},
    {"address": settings.wbtc_address, "symbol": "WBTC", "chain": "evm", "specificChain": "eth"},
]


@dataclass
class AgentState:
    """Observable state exposed to the dashboard."""

    status: str = "initializing"
    portfolio_value: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    initial_value: float = 0.0
    airdrop_score: float = 0.0
    total_trades: int = 0
    last_update: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)


def _combine_signals(signals: dict[str, Signal], weights: dict[str, float]) -> Signal | None:
    """Weighted combination of strategy signals.

    Each strategy votes with its action direction (+1 buy, -1 sell, 0 hold)
    weighted by strategy weight × signal confidence. Returns the winning
    direction if the weighted score exceeds a minimum threshold, else None.
    """
    if not signals:
        return None

    # Group by token — use the token from whichever signal fires
    tokens: set[str] = {s.token for s in signals.values() if s.token and s.action != "hold"}
    if not tokens:
        return None

    best_combined: Signal | None = None
    best_score = 0.0

    for token in tokens:
        weighted_score = 0.0
        reasons: list[str] = []

        for name, signal in signals.items():
            if signal.token != token:
                continue
            w = weights.get(name, 0.0)
            direction = {"buy": 1.0, "sell": -1.0, "hold": 0.0}.get(signal.action, 0.0)
            contribution = w * signal.confidence * direction
            weighted_score += contribution
            if signal.action != "hold":
                reasons.append(f"{name}({signal.action},{signal.confidence:.2f})")

        abs_score = abs(weighted_score)
        if abs_score > best_score:
            best_score = abs_score
            action = "buy" if weighted_score > 0 else "sell"
            reason = f"Weighted [{', '.join(reasons)}] → score={weighted_score:+.3f}"
            best_combined = Signal(action, token, min(abs_score, 1.0), reason)

    # Require a minimum combined score to act (avoids noise trades)
    if best_combined is None or best_score < 0.05:
        return None
    return best_combined


class TradingAgent:
    """Core agent that runs the trading loop."""

    def __init__(self) -> None:
        self.momentum = MomentumStrategy()
        self.mean_reversion = MeanReversionStrategy()
        self.sentiment = SentimentStrategy()
        self.recall_opt = RecallOptimizer()
        self.risk = RiskManager()
        self.state = AgentState()
        self._running = False
        self._client: httpx.AsyncClient | None = None

        # Set diversification targets for airdrop optimizer
        self.recall_opt.set_diversification_targets(
            [t["address"] for t in TRACKED_TOKENS]
        )

    # ------------------------------------------------------------------
    # Recall API helpers
    # ------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=settings.recall_base_url + "/api",
                headers={
                    "Authorization": f"Bearer {settings.recall_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def fetch_portfolio(self) -> dict[str, Any]:
        if settings.simulation_mode:
            return self._sim_portfolio()
        client = await self._get_client()
        resp = await client.get("/agent/portfolio")
        resp.raise_for_status()
        return resp.json()

    async def fetch_price(self, token: str, chain: str = "evm", specific: str = "eth") -> float:
        if settings.simulation_mode:
            return self._sim_price(token)
        client = await self._get_client()
        resp = await client.get(
            "/price", params={"token": token, "chain": chain, "specificChain": specific}
        )
        resp.raise_for_status()
        return float(resp.json().get("price", 0))

    async def execute_trade(
        self, from_token: str, to_token: str, amount: float, reason: str
    ) -> dict[str, Any]:
        if settings.simulation_mode:
            return self._sim_trade(from_token, to_token, amount, reason)
        client = await self._get_client()
        payload = {
            "fromToken": from_token,
            "toToken": to_token,
            "amount": str(amount),
            "reason": reason,
            "competitionId": settings.recall_competition_id,
            "slippageTolerance": settings.slippage_tolerance,
        }
        resp = await client.post("/trade/execute", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def fetch_leaderboard(self) -> dict[str, Any]:
        if settings.simulation_mode:
            return {"entries": [], "simulation": True}
        client = await self._get_client()
        resp = await client.get("/competition/leaderboard")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Simulation helpers
    # ------------------------------------------------------------------

    _sim_prices: dict[str, float] = {}

    def _sim_portfolio(self) -> dict[str, Any]:
        return {
            "success": True,
            "totalValue": self.state.portfolio_value or 10000.0,
            "tokens": [
                {"symbol": "USDC", "token": settings.usdc_address, "amount": 5000, "value": 5000},
                {"symbol": "WETH", "token": settings.weth_address, "amount": 1.5, "value": 2700},
                {"symbol": "WBTC", "token": settings.wbtc_address, "amount": 0.03, "value": 2300},
            ],
        }

    def _sim_price(self, token: str) -> float:
        base = {"WETH": 1800.0, "WBTC": 67000.0}.get(
            next((t["symbol"] for t in TRACKED_TOKENS if t["address"] == token), ""), 1800.0
        )
        if token not in self._sim_prices:
            self._sim_prices[token] = base
        change = random.gauss(0, 0.005)
        self._sim_prices[token] *= 1 + change
        return self._sim_prices[token]

    def _sim_trade(self, from_t: str, to_t: str, amount: float, reason: str) -> dict[str, Any]:
        return {
            "success": True,
            "transaction": {
                "id": f"sim_{int(time.time())}_{random.randint(1000, 9999)}",
                "fromToken": from_t,
                "toToken": to_t,
                "fromAmount": amount,
                "toAmount": amount * 0.998,
                "price": self._sim_prices.get(to_t, 1.0),
                "success": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": reason,
            },
        }

    # ------------------------------------------------------------------
    # Event log
    # ------------------------------------------------------------------

    def _emit(self, event_type: str, message: str, data: dict[str, Any] | None = None) -> None:
        entry = {
            "type": event_type,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data or {},
        }
        self.state.events.append(entry)
        if len(self.state.events) > 200:
            self.state.events = self.state.events[-200:]
        logger.info("[%s] %s", event_type, message)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the agent trading loop."""
        self._running = True
        self.state.status = "running"
        self._emit(
            "agent",
            "Agent started" + (" (SIMULATION)" if settings.simulation_mode else ""),
        )

        portfolio = await self.fetch_portfolio()
        self.state.portfolio_value = portfolio.get("totalValue", 10000.0)
        self.state.initial_value = self.state.portfolio_value
        self.risk.update_portfolio_value(self.state.portfolio_value)

        while self._running:
            try:
                await self._tick()
            except Exception as exc:
                self._emit("error", f"Tick error: {exc}")
                logger.exception("Agent tick failed")
            await asyncio.sleep(settings.trade_interval_seconds)

    async def stop(self) -> None:
        self._running = False
        self.state.status = "stopped"
        self._emit("agent", "Agent stopped")
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def resume(self) -> None:
        """Resume after a risk halt."""
        self.risk.reset()
        self.state.status = "running"
        self._emit("agent", "Agent resumed after risk halt")
        if not self._running:
            await self.start()

    async def _tick(self) -> None:
        """One iteration: fetch prices, evaluate strategies, maybe trade."""
        # 1. Fetch prices & feed all three strategies
        for token_info in TRACKED_TOKENS:
            addr = token_info["address"]
            price = await self.fetch_price(addr, token_info["chain"], token_info["specificChain"])
            self.momentum.feed_price(addr, price)
            self.mean_reversion.feed_price(addr, price)
            self.sentiment.feed_price(addr, price)

        # 2. Refresh portfolio
        portfolio = await self.fetch_portfolio()
        self.state.portfolio_value = portfolio.get("totalValue", self.state.portfolio_value)
        self.risk.update_portfolio_value(self.state.portfolio_value)
        self.state.pnl = self.state.portfolio_value - self.state.initial_value
        self.state.pnl_pct = (
            (self.state.pnl / self.state.initial_value * 100) if self.state.initial_value else 0.0
        )

        # 3. Evaluate all three strategies per token and combine with weights
        best_signal: Signal | None = None
        for token_info in TRACKED_TOKENS:
            addr = token_info["address"]
            per_strategy: dict[str, Signal] = {
                "momentum": self.momentum.evaluate(addr),
                "mean_reversion": self.mean_reversion.evaluate(addr),
                "sentiment": self.sentiment.evaluate(addr),
            }
            combined = _combine_signals(per_strategy, STRATEGY_WEIGHTS)
            if combined and combined.action != "hold":
                if best_signal is None or combined.confidence > best_signal.confidence:
                    best_signal = combined

        # 4. Airdrop optimizer fallback (only when no primary signal)
        if best_signal is None:
            portfolio_tokens = [t.get("token", "") for t in portfolio.get("tokens", [])]
            airdrop_signal = self.recall_opt.evaluate(portfolio_tokens)
            if airdrop_signal.action != "hold":
                best_signal = airdrop_signal

        # 5. Execute trade if we have a signal
        if best_signal and best_signal.action in ("buy", "sell"):
            trade_size = self.risk.optimal_trade_size(
                self.state.portfolio_value, best_signal.confidence
            )
            if trade_size > 0 and self.risk.check_position_size(
                trade_size, self.state.portfolio_value
            ):
                if best_signal.action == "buy":
                    from_token = settings.usdc_address
                    to_token = best_signal.token
                else:
                    from_token = best_signal.token
                    to_token = settings.usdc_address

                result = await self.execute_trade(
                    from_token, to_token, trade_size, best_signal.reason
                )
                if result.get("success"):
                    tx = result.get("transaction", {})
                    self.risk.record_trade(tx)
                    self.recall_opt.record_trade(to_token)
                    self.state.total_trades += 1
                    self._emit(
                        "trade",
                        f"{best_signal.action.upper()} {trade_size:.2f} — {best_signal.reason}",
                        tx,
                    )
                else:
                    self._emit("error", f"Trade failed: {result}")
            else:
                self._emit("risk", f"Trade blocked by risk manager: {best_signal.reason}")
        else:
            self._emit("tick", "No actionable signal this tick")

        # 6. Update airdrop score
        self.state.airdrop_score = self.recall_opt.metrics.estimated_airdrop_score
        self.state.last_update = datetime.now(timezone.utc).isoformat()


# Singleton
agent = TradingAgent()

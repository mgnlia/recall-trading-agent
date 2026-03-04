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

logger = logging.getLogger(__name__)

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


class TradingAgent:
    """Core agent that runs the trading loop."""

    def __init__(self) -> None:
        self.momentum = MomentumStrategy()
        self.mean_reversion = MeanReversionStrategy()
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
        resp = await client.get("/price", params={"token": token, "chain": chain, "specificChain": specific})
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
        # Random walk
        change = random.gauss(0, 0.005)
        self._sim_prices[token] *= 1 + change
        return self._sim_prices[token]

    def _sim_trade(self, from_t: str, to_t: str, amount: float, reason: str) -> dict[str, Any]:
        return {
            "success": True,
            "transaction": {
                "id": f"sim_{int(time.time())}_{random.randint(1000,9999)}",
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
        self._emit("agent", "Agent started" + (" (SIMULATION)" if settings.simulation_mode else ""))

        # Initial portfolio snapshot
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

    async def _tick(self) -> None:
        """One iteration: fetch prices, evaluate strategies, maybe trade."""
        # 1. Fetch prices & feed strategies
        for token_info in TRACKED_TOKENS:
            addr = token_info["address"]
            price = await self.fetch_price(addr, token_info["chain"], token_info["specificChain"])
            self.momentum.feed_price(addr, price)
            self.mean_reversion.feed_price(addr, price)

        # 2. Refresh portfolio
        portfolio = await self.fetch_portfolio()
        self.state.portfolio_value = portfolio.get("totalValue", self.state.portfolio_value)
        self.risk.update_portfolio_value(self.state.portfolio_value)
        self.state.pnl = self.state.portfolio_value - self.state.initial_value
        self.state.pnl_pct = (
            (self.state.pnl / self.state.initial_value * 100) if self.state.initial_value else 0.0
        )

        # 3. Evaluate strategies
        best_signal: Signal | None = None
        for token_info in TRACKED_TOKENS:
            addr = token_info["address"]
            for strategy in [self.momentum, self.mean_reversion]:
                signal = strategy.evaluate(addr)
                if signal.action != "hold":
                    if best_signal is None or signal.confidence > best_signal.confidence:
                        best_signal = signal

        # 4. Airdrop optimizer fallback
        if best_signal is None or best_signal.action == "hold":
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

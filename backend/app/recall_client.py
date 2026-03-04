"""
Recall Competition API client.

Official API docs: https://docs.recall.network/competitions/build-agent/trading
Base URL (prod):    https://api.competitions.recall.network/api
Base URL (sandbox): https://api.sandbox.competitions.recall.network/api

Auth: Bearer token in Authorization header.
"""
import asyncio
import structlog
from typing import Any, Optional
from dataclasses import dataclass

import httpx

from app.config import settings

logger = structlog.get_logger(__name__)

# Well-known ERC-20 addresses (mainnet fork — sandbox uses same addresses)
TOKENS = {
    "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
    "DAI":  "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    "LINK": "0x514910771AF9Ca656af840dff83E8264EcF986CA",
    "UNI":  "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
    "AAVE": "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9",
    "SOL":  "So11111111111111111111111111111111111111112",  # Solana native
}

# Chain constants
EVM_CHAIN = "evm"
SVM_CHAIN = "svm"
ETH_SPECIFIC = "eth"
BASE_SPECIFIC = "base"
SOL_SPECIFIC = "solana"


@dataclass
class TokenBalance:
    token: str
    symbol: str
    amount: float
    price: float
    value: float
    chain: str


@dataclass
class Portfolio:
    agent_id: str
    total_value: float
    tokens: list[TokenBalance]
    snapshot_time: str


@dataclass
class TradeResult:
    success: bool
    transaction_id: str
    from_token: str
    to_token: str
    from_amount: float
    to_amount: float
    price: float
    timestamp: str
    error: str = ""


@dataclass
class TokenPrice:
    token: str
    price: float
    chain: str
    specific_chain: str


class RecallClient:
    """
    Async HTTP client for the Recall Competition API.
    All methods raise on non-2xx responses.
    """

    def __init__(self):
        self._api_key = settings.recall_api_key
        self._base_url = settings.api_base

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @property
    def has_credentials(self) -> bool:
        return bool(self._api_key)

    async def get_portfolio(self) -> Portfolio:
        """GET /agent/portfolio — current balances and total value."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self._base_url}/agent/portfolio",
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()

        tokens = [
            TokenBalance(
                token=t.get("token", ""),
                symbol=t.get("symbol", "UNKNOWN"),
                amount=float(t.get("amount", 0)),
                price=float(t.get("price", 0)),
                value=float(t.get("value", 0)),
                chain=t.get("chain", "evm"),
            )
            for t in data.get("tokens", [])
        ]

        return Portfolio(
            agent_id=data.get("agentId", ""),
            total_value=float(data.get("totalValue", 0)),
            tokens=tokens,
            snapshot_time=data.get("snapshotTime", ""),
        )

    async def get_price(
        self,
        token_address: str,
        chain: str = EVM_CHAIN,
        specific_chain: str = ETH_SPECIFIC,
    ) -> TokenPrice:
        """GET /price — current price of a token."""
        params = {
            "token": token_address,
            "chain": chain,
            "specificChain": specific_chain,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self._base_url}/price",
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        return TokenPrice(
            token=token_address,
            price=float(data.get("price", 0)),
            chain=data.get("chain", chain),
            specific_chain=data.get("specificChain", specific_chain),
        )

    async def execute_trade(
        self,
        from_token: str,
        to_token: str,
        amount: float,
        from_chain: str = EVM_CHAIN,
        to_chain: str = EVM_CHAIN,
        from_specific_chain: str = ETH_SPECIFIC,
        to_specific_chain: str = ETH_SPECIFIC,
        reason: str = "",
    ) -> TradeResult:
        """POST /trade/execute — submit a swap."""
        payload: dict[str, Any] = {
            "fromToken": from_token,
            "toToken": to_token,
            "amount": str(amount),
            "fromChain": from_chain,
            "toChain": to_chain,
            "fromSpecificChain": from_specific_chain,
            "toSpecificChain": to_specific_chain,
        }
        if reason:
            payload["reason"] = reason

        logger.info(
            "recall.trade_submit",
            from_token=from_token,
            to_token=to_token,
            amount=amount,
            reason=reason,
        )

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self._base_url}/trade/execute",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            tx = data.get("transaction", {})
            result = TradeResult(
                success=data.get("success", False),
                transaction_id=tx.get("id", ""),
                from_token=tx.get("fromToken", from_token),
                to_token=tx.get("toToken", to_token),
                from_amount=float(tx.get("fromAmount", 0)),
                to_amount=float(tx.get("toAmount", 0)),
                price=float(tx.get("price", 0)),
                timestamp=tx.get("timestamp", ""),
            )
            logger.info(
                "recall.trade_success",
                tx_id=result.transaction_id,
                from_amount=result.from_amount,
                to_amount=result.to_amount,
                price=result.price,
            )
            return result

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error("recall.trade_failed", error=error_msg)
            return TradeResult(
                success=False,
                transaction_id="",
                from_token=from_token,
                to_token=to_token,
                from_amount=amount,
                to_amount=0,
                price=0,
                timestamp="",
                error=error_msg,
            )

    async def get_leaderboard(self) -> list[dict]:
        """GET /competition/leaderboard — current competition rankings."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self._base_url}/competition/leaderboard",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
            return data if isinstance(data, list) else data.get("agents", [])
        except Exception as e:
            logger.warning("recall.leaderboard_error", error=str(e))
            return []

    async def get_prices_batch(
        self,
        tokens: list[tuple[str, str, str]],  # (address, chain, specific_chain)
    ) -> dict[str, float]:
        """Fetch prices for multiple tokens concurrently."""
        async def _fetch(addr: str, chain: str, specific: str) -> tuple[str, float]:
            try:
                p = await self.get_price(addr, chain, specific)
                return addr, p.price
            except Exception as e:
                logger.warning("recall.price_fetch_error", token=addr, error=str(e))
                return addr, 0.0

        results = await asyncio.gather(*[_fetch(a, c, s) for a, c, s in tokens])
        return dict(results)

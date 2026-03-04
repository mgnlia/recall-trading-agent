"""
Base class for all trading strategies.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class TradeSignal:
    signal: Signal
    from_token: str
    to_token: str
    from_symbol: str
    to_symbol: str
    strength: float          # 0.0 to 1.0 — how confident we are
    reason: str
    strategy_name: str
    from_chain: str = "evm"
    to_chain: str = "evm"
    from_specific_chain: str = "eth"
    to_specific_chain: str = "eth"


class BaseStrategy(ABC):
    """
    All strategies must implement `generate_signal`.
    They receive the price history dict and current portfolio,
    and return a TradeSignal (or None to pass).
    """

    name: str = "base"

    @abstractmethod
    async def generate_signal(
        self,
        price_history: dict[str, list[float]],  # token_address -> [prices oldest..newest]
        portfolio_value: float,
        token_balances: dict[str, float],        # symbol -> USD value
    ) -> Optional[TradeSignal]:
        ...

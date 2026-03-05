"""Application settings — all fields used by agent.py and risk.py are defined here.

Every ``settings.<attr>`` reference in the codebase must have a matching field.
Add a comment next to any field whose name differs from an obvious alternative
so future readers don't rename it back to something broken.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # -----------------------------------------------------------------------
    # Recall Network API
    # -----------------------------------------------------------------------
    # NOTE: field is recall_base_url, NOT api_base_url — agent.py uses this name
    recall_base_url: str = "https://api.recall.network"
    recall_api_key: str = ""
    recall_competition_id: str = ""

    # -----------------------------------------------------------------------
    # Agent behaviour
    # -----------------------------------------------------------------------
    simulation_mode: bool = True
    agent_name: str = "RecallTrader-v1"
    trade_interval_seconds: int = 30
    slippage_tolerance: float = 0.005   # 0.5 %

    # -----------------------------------------------------------------------
    # Risk limits
    # NOTE: max_drawdown_pct and max_position_pct are the names used in risk.py.
    #       Do NOT rename to risk_per_trade / max_position_size.
    # -----------------------------------------------------------------------
    max_drawdown_pct: float = 0.15      # halt if drawdown exceeds 15 %
    max_position_pct: float = 0.25      # max 25 % of portfolio per trade

    # -----------------------------------------------------------------------
    # Token addresses (Ethereum mainnet)
    # -----------------------------------------------------------------------
    usdc_address: str = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    weth_address: str = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    wbtc_address: str = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

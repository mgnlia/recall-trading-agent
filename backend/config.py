"""Configuration via environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """App settings loaded from env vars / .env file."""

    # Recall API
    recall_api_key: str = "demo_key"
    recall_base_url: str = "https://api.sandbox.competitions.recall.network"
    recall_competition_id: str = ""

    # Agent behaviour
    simulation_mode: bool = True
    trade_interval_seconds: int = 60
    max_position_pct: float = 0.25  # max 25% of portfolio in one token
    max_drawdown_pct: float = 0.15  # stop trading if drawdown > 15%
    slippage_tolerance: str = "0.5"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    # Well-known token addresses (Ethereum mainnet fork)
    usdc_address: str = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    weth_address: str = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    wbtc_address: str = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

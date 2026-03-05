from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # General
    simulation_mode: bool = True
    agent_name: str = "RecallTrader-v1"
    trade_interval_seconds: int = 30

    # Recall Network API
    api_base_url: str = "http://localhost:8000"
    recall_base_url: str = "https://api.recall.network"
    recall_api_key: str = ""
    recall_competition_id: str = ""

    # Polymarket (for airdrop farming)
    polymarket_api_key: str = ""

    # Risk management
    max_position_size: float = 100.0
    max_position_pct: float = 0.25
    max_drawdown_pct: float = 0.15
    risk_per_trade: float = 0.02
    slippage_tolerance: float = 0.01

    # Token addresses (Ethereum mainnet defaults)
    weth_address: str = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    wbtc_address: str = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
    usdc_address: str = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

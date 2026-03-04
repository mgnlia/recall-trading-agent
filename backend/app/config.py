"""
Configuration — all settings from environment variables.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Recall API
    recall_api_key: str = ""
    use_sandbox: bool = True  # default to sandbox for safety

    # Agent metadata
    agent_name: str = "recall-ai-agent"

    # Trading parameters
    trade_interval_secs: int = 60          # how often to run the main loop
    max_position_pct: float = 0.25         # max 25% of portfolio in single token
    max_trade_pct: float = 0.10            # max 10% of portfolio per trade
    min_trade_usd: float = 10.0            # minimum trade size in USD
    max_daily_drawdown_pct: float = 0.10   # halt if portfolio drops >10% from peak

    # Strategy weights (must sum to 1.0)
    momentum_weight: float = 0.5
    mean_revert_weight: float = 0.3
    sentiment_weight: float = 0.2

    # Momentum strategy
    momentum_window: int = 5               # number of price samples to look back
    momentum_threshold: float = 0.015     # 1.5% move to trigger signal

    # Mean reversion strategy
    mean_revert_window: int = 10
    mean_revert_z_threshold: float = 1.5   # z-score threshold

    # Logging
    log_level: str = "INFO"

    @property
    def base_url(self) -> str:
        if self.use_sandbox:
            return "https://api.sandbox.competitions.recall.network"
        return "https://api.competitions.recall.network"

    @property
    def api_base(self) -> str:
        return f"{self.base_url}/api"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

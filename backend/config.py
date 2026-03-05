from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    simulation_mode: bool = True
    api_base_url: str = "http://localhost:8000"
    recall_api_key: str = ""
    polymarket_api_key: str = ""
    agent_name: str = "RecallTrader-v1"
    trade_interval_seconds: int = 30
    max_position_size: float = 100.0
    risk_per_trade: float = 0.02

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # General
    LOG_LEVEL: str = "INFO"
    ENV: str = "development"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str

    # DexScreener
    DEXSCREENER_API_URL: str = "https://api.dexscreener.com/latest/dex/pairs"
    
    # AI
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    AI_PROVIDER: str = "deepseek" # 'openai', 'gemini', or 'deepseek'
    AI_MODEL: str = "deepseek-chat" # Default to deepseek-chat
    AI_CONFIDENCE_THRESHOLD: float = 0.7

    # Fixed / Hard Filters
    MIN_LIQUIDITY_USD: float = 10000.0
    MIN_PAIR_AGE_MINUTES: int = 2

    # Security
    GOPLUS_API_KEY: Optional[str] = None
    GOPLUS_API_SECRET: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

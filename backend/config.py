"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the API."""

    gemini_api_key: str
    gemini_model: str = "gemini-flash-lite-latest"
    cache_db_path: str = "data/timesense.db"
    low_confidence_threshold: float = 0.5
    ema_alpha: float = 0.3
    few_shot_path: str = "prompts/few_shot.json"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()

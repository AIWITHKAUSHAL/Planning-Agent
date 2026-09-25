"""Environment-backed configuration for the planning-agent application."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Define runtime settings loaded from environment variables and ``.env``."""

    euri_api_key: str = ""
    euri_base_url: str = "https://api.euron.one/api/v1/euri"
    euri_model: str = "gemini-3.5-flash-lite"
    demo_mode: bool = False
    max_retries: int = 2
    max_replans: int = 1
    database_path: Path = Path("data/planning_agent.db")
    output_dir: Path = Path("outputs")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance for consistent process-wide configuration."""
    return Settings()

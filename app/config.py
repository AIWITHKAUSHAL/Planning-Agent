from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    demo_mode: bool = False
    max_retries: int = 2
    max_replans: int = 1
    database_path: Path = Path("data/planning_agent.db")
    output_dir: Path = Path("outputs")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


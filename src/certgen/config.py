"""Application configuration via pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_prefix="CERTGEN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database settings
    database_url: str = "sqlite:///./data/certgen.db"

    # Storage settings
    storage_dir: Path = Path("./storage/certificates")

    # Processing settings
    max_recipients_per_job: int = 1000
    disable_recovery: bool = False

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()

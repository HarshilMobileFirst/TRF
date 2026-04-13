from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TRF Scanner MVP"
    env: str = "development"
    log_level: str = "INFO"
    auth_username: str = "admin"
    auth_password: str = "changeme"
    storage_root: Path = Path("storage")
    uploads_dir: str = "uploads"
    processed_dir: str = "processed"
    corrected_dir: str = "corrected"
    approved_dir: str = "approved"
    ocr_provider: str = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.1"
    openai_timeout_seconds: int = 90
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    sample_duplicate_window_days: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

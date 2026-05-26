from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_NAME: str = "Military Personnel Leave Management System"
    APP_ENV: Literal["local", "development", "testing", "production"] = "local"
    DEBUG: bool = False

    BOT_TOKEN: SecretStr | None = None

    DATABASE_URL: str = (
        "postgresql+asyncpg://mplms:mplms@localhost:5432/mplms"
    )

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @property
    def bot_token_value(self) -> str | None:
        if self.BOT_TOKEN is None:
            return None
        return self.BOT_TOKEN.get_secret_value()


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()


settings = get_settings()

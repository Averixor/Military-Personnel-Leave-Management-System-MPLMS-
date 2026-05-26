from __future__ import annotations

import logging
from functools import lru_cache
from logging.config import dictConfig
from typing import Literal

from pydantic import field_validator
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from mplms.core.database import resolve_database_url


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

    # Empty = dev SQLite default (see mplms.core.database.resolve_database_url).
    DATABASE_URL: str = ""

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug_flag(cls, value: object) -> object:
        if isinstance(value, str) and value.lower() == "release":
            return False
        return value

    @property
    def database_url(self) -> str:
        explicit = self.DATABASE_URL.strip() if self.DATABASE_URL else None
        return resolve_database_url(explicit)

    @property
    def telegram_bot_token(self) -> str | None:
        return self.bot_token_value

    @property
    def bot_token_value(self) -> str | None:
        if self.BOT_TOKEN is None:
            return None
        return self.BOT_TOKEN.get_secret_value()


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()


settings = get_settings()


def configure_logging() -> None:
    cfg = get_settings()
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "root": {
                "handlers": ["console"],
                "level": cfg.LOG_LEVEL,
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

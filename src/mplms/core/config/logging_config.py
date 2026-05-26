from __future__ import annotations

import logging
from logging.config import dictConfig

from mplms.core.config.settings import get_settings


def configure_logging() -> None:
    settings = get_settings()

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
                "level": settings.LOG_LEVEL,
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

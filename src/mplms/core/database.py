"""Database URL resolution and engine helpers (SQLite dev / PostgreSQL prod)."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

DEV_SQLITE_URL = "sqlite+aiosqlite:///./data/mplms_dev.sqlite3"


def resolve_database_url(explicit: str | None = None) -> str:
    """Return DATABASE_URL from explicit value, env, or the dev SQLite default."""
    if explicit is not None:
        url = explicit.strip()
    else:
        url = (os.getenv("DATABASE_URL") or "").strip()
    if url:
        return url
    return DEV_SQLITE_URL


def is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def is_postgresql(url: str) -> bool:
    return url.startswith("postgresql")


def sqlite_database_path(url: str) -> Path | None:
    if not is_sqlite(url):
        return None
    parsed = urlparse(url.replace("sqlite+aiosqlite:", "sqlite:", 1))
    if not parsed.path or parsed.path in (":memory:", "/:memory:"):
        return None
    raw = parsed.path.lstrip("/")
    if os.name == "nt" and len(raw) > 1 and raw[1] == ":":
        return Path(raw)
    return Path(raw)


def ensure_sqlite_data_dir(url: str) -> Path | None:
    """Create parent directory for a file-based SQLite database."""
    db_path = sqlite_database_path(url)
    if db_path is None:
        return None
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path.parent


def alembic_sync_url(async_url: str) -> str:
    """Map async SQLAlchemy URLs to sync drivers for Alembic."""
    if async_url.startswith("postgresql+asyncpg://"):
        return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if async_url.startswith("sqlite+aiosqlite://"):
        return async_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return async_url


def engine_kwargs(url: str) -> dict:
    kwargs: dict = {"pool_pre_ping": True}
    if is_sqlite(url) and ":memory:" not in url:
        kwargs["connect_args"] = {"timeout": 30}
    return kwargs

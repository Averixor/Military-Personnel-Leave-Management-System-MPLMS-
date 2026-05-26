from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy import pool

import mplms.models  # noqa: F401 — register all ORM tables on Base.metadata
from mplms.core.database import alembic_sync_url
from mplms.core.database import resolve_database_url
from mplms.models import Base

config = context.config


def _migration_url() -> str:
    env_url = os.getenv("DATABASE_URL", "").strip()
    url = resolve_database_url(env_url or None)
    return alembic_sync_url(url)


if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = _migration_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    if configuration is None:
        configuration = {}
    configuration["sqlalchemy.url"] = _migration_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=configuration["sqlalchemy.url"].startswith("sqlite"),
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

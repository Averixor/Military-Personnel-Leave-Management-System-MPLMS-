"""SQLite dev database helpers for the Telegram bot layer."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

import mplms.models  # noqa: F401
from mplms.core.database import ensure_sqlite_data_dir
from mplms.core.database import engine_kwargs
from mplms.core.database import resolve_database_url
from mplms.domain.enums import UserRole
from mplms.models import Base
from mplms.models.personnel import Personnel
from mplms.models.personnel import Unit
from mplms.models.policy import PolicySnapshot

BOT_UNIT_NAME = "Telegram Bot Unit"

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _engine, _session_factory
    if _session_factory is not None:
        return _session_factory

    url = resolve_database_url(None)
    ensure_sqlite_data_dir(url)
    _engine = create_async_engine(url, **engine_kwargs(url))
    async with _engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, autobegin=False)
    return _session_factory


async def ensure_personnel_for_telegram(
    session_factory: async_sessionmaker[AsyncSession],
    telegram_user_id: int,
    display_name: str | None,
) -> str:
    async with session_factory() as session, session.begin():
        person = await session.scalar(
            select(Personnel).where(Personnel.telegram_id == telegram_user_id)
        )
        if person is not None:
            return str(person.id)

        unit = await session.scalar(select(Unit).where(Unit.name == BOT_UNIT_NAME))
        if unit is None:
            unit = Unit(name=BOT_UNIT_NAME, normal_overlap_limit=2)
            session.add(unit)
            await session.flush()

        policy = await session.scalar(
            select(PolicySnapshot).where(PolicySnapshot.is_active.is_(True)).limit(1)
        )
        if policy is None:
            policy = PolicySnapshot(
                legal_rules_version="bot-mvp-legal",
                internal_policy_version="bot-mvp-internal",
                legal_rules={},
                internal_rules={},
                effective_from=date(2026, 1, 1),
                is_active=True,
            )
            session.add(policy)
            await session.flush()

        person = Personnel(
            telegram_id=telegram_user_id,
            full_name=display_name or f"Telegram user {telegram_user_id}",
            role=UserRole.PERSONNEL,
            unit_id=unit.id,
        )
        session.add(person)
        await session.flush()
        return str(person.id)

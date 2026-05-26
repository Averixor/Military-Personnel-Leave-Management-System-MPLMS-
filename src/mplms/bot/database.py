"""SQLite dev database helpers for the Telegram bot layer."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

import mplms.models  # noqa: F401
from mplms.core.config import get_settings
from mplms.core.database import ensure_sqlite_data_dir
from mplms.core.database import engine_kwargs
from mplms.core.database import resolve_database_url
from mplms.domain.enums import UserRole
from mplms.models import Base
from mplms.models.personnel import Personnel
from mplms.models.personnel import Unit
from mplms.models.policy import PolicySnapshot

BOT_UNIT_NAME = "Telegram Bot Unit"
DEMO_ADMIN_NAME = "Telegram Demo Admin"
DEMO_COMMANDER_NAME = "Telegram Demo Commander"
PERSONNEL_NOT_IN_DATABASE_MESSAGE = (
    "Вас не знайдено в базі. Зверніться до адміністратора."
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


class TelegramPersonnelNotFoundError(LookupError):
    """Raised when telegram_id is absent in personnel and auto-create is disabled."""

    def __init__(self, telegram_user_id: int) -> None:
        self.telegram_user_id = telegram_user_id
        super().__init__(PERSONNEL_NOT_IN_DATABASE_MESSAGE)


class InactivePersonnelError(PermissionError):
    def __init__(self, personnel: Personnel) -> None:
        self.personnel = personnel
        super().__init__(
            f"Personnel #{personnel.id} is inactive and cannot use bot commands."
        )


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
    *,
    auto_create: bool | None = None,
    require_active: bool = True,
) -> Personnel:
    async with session_factory() as session, session.begin():
        person = await ensure_personnel_in_session(
            session,
            telegram_user_id=telegram_user_id,
            display_name=display_name,
            auto_create=auto_create,
            require_active=require_active,
        )
        await ensure_policy_in_session(session)
        return person


async def ensure_personnel_in_session(
    session: AsyncSession,
    telegram_user_id: int,
    display_name: str | None,
    *,
    auto_create: bool | None = None,
    require_active: bool = True,
) -> Personnel:
    person = await session.scalar(
        select(Personnel).where(Personnel.telegram_id == telegram_user_id)
    )
    if person is not None:
        if require_active and not person.is_active:
            raise InactivePersonnelError(person)
        return person

    should_auto_create = (
        get_settings().BOT_AUTO_CREATE_PERSONNEL if auto_create is None else auto_create
    )
    if not should_auto_create:
        raise TelegramPersonnelNotFoundError(telegram_user_id)

    unit = await ensure_bot_unit_in_session(session)
    await ensure_policy_in_session(session)

    person = Personnel(
        telegram_id=telegram_user_id,
        full_name=display_name or f"Telegram user {telegram_user_id}",
        role=UserRole.PERSONNEL,
        unit_id=unit.id,
    )
    session.add(person)
    await session.flush()
    return person


async def ensure_bot_unit_in_session(session: AsyncSession) -> Unit:
    unit = await session.scalar(select(Unit).where(Unit.name == BOT_UNIT_NAME))
    if unit is None:
        unit = Unit(name=BOT_UNIT_NAME, normal_overlap_limit=2)
        session.add(unit)
        await session.flush()
    return unit


async def ensure_policy_in_session(session: AsyncSession) -> PolicySnapshot:
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
    return policy


async def ensure_demo_commander(
    session_factory: async_sessionmaker[AsyncSession],
) -> str:
    return await _ensure_demo_role(
        session_factory,
        full_name=DEMO_COMMANDER_NAME,
        role=UserRole.COMMANDER,
    )


async def ensure_demo_admin(
    session_factory: async_sessionmaker[AsyncSession],
) -> str:
    return await _ensure_demo_role(
        session_factory,
        full_name=DEMO_ADMIN_NAME,
        role=UserRole.ADMIN,
    )


async def _ensure_demo_role(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    full_name: str,
    role: UserRole,
) -> str:
    async with session_factory() as session, session.begin():
        person = await session.scalar(select(Personnel).where(Personnel.full_name == full_name))
        if person is not None:
            return str(person.id)

        unit = await ensure_bot_unit_in_session(session)
        await ensure_policy_in_session(session)
        person = Personnel(
            full_name=full_name,
            role=role,
            unit_id=unit.id,
        )
        session.add(person)
        await session.flush()
        return str(person.id)

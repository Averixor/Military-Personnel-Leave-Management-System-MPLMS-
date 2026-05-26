from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from mplms.core.config import get_settings
from mplms.core.database import engine_kwargs
from mplms.core.database import ensure_sqlite_data_dir

_settings = get_settings()
ensure_sqlite_data_dir(_settings.database_url)

engine = create_async_engine(
    _settings.database_url,
    **engine_kwargs(_settings.database_url),
)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session

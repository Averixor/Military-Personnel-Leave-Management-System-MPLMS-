import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

import mplms.models  # noqa: F401
from mplms.models import Base


@pytest.mark.asyncio
async def test_metadata_creates_tables_on_sqlite_memory() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with engine.connect() as connection:
            table_names = await connection.run_sync(
                lambda sync_conn: set(inspect(sync_conn).get_table_names())
            )

        expected = {
            "personnel",
            "leave_periods",
            "leave_requests",
            "approval_steps",
            "conflict_groups",
            "policy_snapshots",
            "audit_logs",
            "snapshots",
            "documents",
            "override_audits",
        }
        assert expected.issubset(table_names)
    finally:
        await engine.dispose()

import os
from collections.abc import AsyncIterator
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from mplms.domain.enums import LeaveStatus
from mplms.domain.enums import LeaveType
from mplms.domain.enums import RequestStatus
from mplms.domain.enums import UserRole
from mplms.models.leave import LeavePeriod
from mplms.models.personnel import Personnel
from mplms.models.personnel import Unit
from mplms.models.policy import PolicySnapshot
from mplms.models.workflow import LeaveRequest
from mplms.models.workflow import RequestOption

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://mplms:mplms@localhost:5432/mplms",
)


def _postgres_available() -> bool:
    try:
        import asyncio

        async def _ping() -> bool:
            engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
            try:
                async with engine.connect() as connection:
                    await connection.execute(select(1))
                return True
            finally:
                await engine.dispose()

        return asyncio.run(_ping())
    except Exception:
        return False


requires_postgres = pytest.mark.skipif(
    not _postgres_available(),
    reason="PostgreSQL is required for integration tests",
)


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with session_factory(bind=connection) as session:
            yield session
        await transaction.rollback()

    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_ready_request(db_session: AsyncSession) -> dict:
    unit = Unit(name="Test Unit Alpha", normal_overlap_limit=2)
    db_session.add(unit)
    await db_session.flush()

    policy = PolicySnapshot(
        legal_rules_version="test-legal",
        internal_policy_version="test-internal",
        legal_rules={},
        internal_rules={},
        effective_from=date(2026, 1, 1),
        is_active=True,
    )
    db_session.add(policy)
    await db_session.flush()

    admin = Personnel(full_name="Admin User", role=UserRole.ADMIN, unit_id=unit.id)
    applicant = Personnel(full_name="Applicant User", role=UserRole.PERSONNEL, unit_id=unit.id)
    db_session.add_all([admin, applicant])
    await db_session.flush()

    leave = LeavePeriod(
        person_id=applicant.id,
        leave_type=LeaveType.ANNUAL_MAIN,
        year=2026,
        starts_on=date(2026, 7, 1),
        ends_on=date(2026, 7, 15),
        days_count=15,
        initial_starts_on=date(2026, 7, 1),
        initial_ends_on=date(2026, 7, 15),
        status=LeaveStatus.PLANNED,
        is_frozen=False,
        policy_snapshot_id=policy.id,
    )
    db_session.add(leave)
    await db_session.flush()

    request = LeaveRequest(
        person_id=applicant.id,
        desired_start_date=date(2026, 8, 1),
        desired_days_count=15,
        status=RequestStatus.READY_TO_APPLY,
        policy_snapshot_id=policy.id,
    )
    db_session.add(request)
    await db_session.flush()

    new_start = date(2026, 8, 1)
    new_end = date(2026, 8, 15)
    option = RequestOption(
        request_id=request.id,
        proposed_start_date=new_start,
        proposed_end_date=new_end,
        conflict_score=0,
        overlap_level=0,
        explanation={
            "leave_changes": [
                {
                    "leave_id": leave.id,
                    "starts_on": new_start.isoformat(),
                    "ends_on": new_end.isoformat(),
                }
            ],
            "option_fingerprint": {
                "proposed_start_date": new_start.isoformat(),
                "proposed_end_date": new_end.isoformat(),
                "overlap_level": 0,
            },
        },
    )
    db_session.add(option)
    await db_session.flush()

    request.selected_option_id = option.id
    await db_session.flush()

    return {
        "admin_id": admin.id,
        "applicant_id": applicant.id,
        "leave_id": leave.id,
        "request_id": request.id,
        "option_id": option.id,
        "new_start": new_start,
        "new_end": new_end,
    }

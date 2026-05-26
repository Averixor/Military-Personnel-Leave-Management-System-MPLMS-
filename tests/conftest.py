import os
from collections.abc import AsyncIterator
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

import mplms.models  # noqa: F401
from mplms.domain.enums import LeaveStatus
from mplms.domain.enums import LeaveType
from mplms.domain.enums import RequestStatus
from mplms.domain.enums import UserRole
from mplms.models import Base
from mplms.models.leave import LeavePeriod
from mplms.models.personnel import Personnel
from mplms.models.personnel import Unit
from mplms.models.policy import PolicySnapshot
from mplms.models.workflow import LeaveRequest
from mplms.models.workflow import RequestOption

# Integration tests always use in-memory SQLite (ignore .env PostgreSQL).
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(
        db_engine,
        expire_on_commit=False,
        autobegin=False,
    )
    async with session_factory() as session:
        try:
            yield session
        finally:
            if session.in_transaction():
                await session.rollback()


@pytest_asyncio.fixture
async def seeded_ready_request(db_engine: AsyncEngine) -> dict:
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session, session.begin():
        unit = Unit(name="Test Unit Alpha", normal_overlap_limit=2)
        session.add(unit)
        await session.flush()

        policy = PolicySnapshot(
            legal_rules_version="test-legal",
            internal_policy_version="test-internal",
            legal_rules={},
            internal_rules={},
            effective_from=date(2026, 1, 1),
            is_active=True,
        )
        session.add(policy)
        await session.flush()

        admin = Personnel(full_name="Admin User", role=UserRole.ADMIN, unit_id=unit.id)
        applicant = Personnel(full_name="Applicant User", role=UserRole.PERSONNEL, unit_id=unit.id)
        session.add_all([admin, applicant])
        await session.flush()

        new_start = date(2026, 8, 1)
        new_end = date(2026, 8, 15)
        leave = LeavePeriod(
            person_id=applicant.id,
            leave_type=LeaveType.ANNUAL_MAIN,
            year=2026,
            starts_on=date(2026, 7, 30),
            ends_on=date(2026, 8, 13),
            days_count=15,
            initial_starts_on=new_start,
            initial_ends_on=new_end,
            status=LeaveStatus.PLANNED,
            is_frozen=False,
            policy_snapshot_id=policy.id,
        )
        session.add(leave)
        await session.flush()

        request = LeaveRequest(
            person_id=applicant.id,
            desired_start_date=date(2026, 8, 1),
            desired_days_count=15,
            status=RequestStatus.READY_TO_APPLY,
            policy_snapshot_id=policy.id,
        )
        session.add(request)
        await session.flush()

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
        session.add(option)
        await session.flush()

        request.selected_option_id = option.id
        await session.flush()

        return {
            "admin_id": admin.id,
            "applicant_id": applicant.id,
            "leave_id": leave.id,
            "request_id": request.id,
            "option_id": option.id,
            "new_start": new_start,
            "new_end": new_end,
        }

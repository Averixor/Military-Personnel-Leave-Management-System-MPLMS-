from datetime import date

import pytest
from sqlalchemy import select

from mplms.domain.enums import LeaveStatus
from mplms.domain.enums import LeaveType
from mplms.domain.enums import RequestStatus
from mplms.domain.enums import UserRole
from mplms.models.leave import LeavePeriod
from mplms.models.personnel import Personnel
from mplms.models.personnel import Unit
from mplms.models.policy import PolicySnapshot
from mplms.models.workflow import LeaveRequest
from mplms.services.leave_request import STATUS_OPTIONS_GENERATED
from mplms.services.leave_request_persistence import create_persisted_leave_request
from mplms.services.leave_request_persistence import select_persisted_leave_option
from mplms.services.scheduler import ScheduleOption


@pytest.mark.asyncio
async def test_create_persisted_request_creates_row(db_session) -> None:
    person_id, _policy_id = await _seed_person(db_session)

    result = await create_persisted_leave_request(
        db_session,
        personnel_id=person_id,
        desired_start=date(2026, 6, 15),
        duration_days=10,
        leave_type=LeaveType.ANNUAL_MAIN.value,
        max_shift_days=2,
    )

    assert result.status == STATUS_OPTIONS_GENERATED
    assert result.options

    async with db_session.begin():
        row = await db_session.get(LeaveRequest, int(result.request_id))
        assert row is not None
        assert row.person_id == int(person_id)
        assert row.desired_start_date == date(2026, 6, 15)
        assert row.desired_days_count == 10
        assert row.status == RequestStatus.OPTIONS_GENERATED


@pytest.mark.asyncio
async def test_existing_leave_period_affects_scheduler_score(db_session) -> None:
    person_id, policy_id = await _seed_person(db_session)

    async with db_session.begin():
        db_session.add(
            LeavePeriod(
                person_id=int(person_id),
                leave_type=LeaveType.ANNUAL_MAIN,
                year=2026,
                starts_on=date(2026, 6, 10),
                ends_on=date(2026, 6, 20),
                days_count=11,
                initial_starts_on=date(2026, 6, 10),
                initial_ends_on=date(2026, 6, 20),
                status=LeaveStatus.PLANNED,
                is_frozen=False,
                policy_snapshot_id=policy_id,
            )
        )

    result = await create_persisted_leave_request(
        db_session,
        personnel_id=person_id,
        desired_start=date(2026, 6, 15),
        duration_days=10,
        leave_type=LeaveType.ANNUAL_MAIN.value,
        max_shift_days=0,
    )

    assert result.options[0].overlap_count == 1
    assert result.options[0].conflict_score > 0


@pytest.mark.asyncio
async def test_select_option_creates_leave_period_and_updates_status(db_session) -> None:
    person_id, _policy_id = await _seed_person(db_session)

    created = await create_persisted_leave_request(
        db_session,
        personnel_id=person_id,
        desired_start=date(2026, 6, 15),
        duration_days=5,
        leave_type=LeaveType.ANNUAL_MAIN.value,
        max_shift_days=0,
    )
    option = created.options[0]

    updated = await select_persisted_leave_option(
        db_session,
        request_id=created.request_id,
        option=option,
    )

    assert updated.status == RequestStatus.SELECTED_BY_USER

    async with db_session.begin():
        request = await db_session.get(LeaveRequest, int(created.request_id))
        assert request is not None
        assert request.status == RequestStatus.SELECTED_BY_USER
        assert request.selected_leave_period_id is not None

        leaves = (
            await db_session.execute(
                select(LeavePeriod).where(LeavePeriod.source_request_id == request.id)
            )
        ).scalars().all()
        assert len(leaves) == 1
        assert leaves[0].starts_on == option.start_date
        assert leaves[0].ends_on == option.end_date


@pytest.mark.asyncio
async def test_select_invalid_request_id_raises(db_session) -> None:
    await _seed_person(db_session)
    option = ScheduleOption(
        start_date=date(2026, 6, 15),
        end_date=date(2026, 6, 19),
        duration_days=5,
        conflict_score=0,
        overlap_count=0,
        max_absent_on_any_day=1,
        reasons=["no staffing conflicts"],
    )

    with pytest.raises(ValueError, match="not found"):
        await select_persisted_leave_option(
            db_session,
            request_id="99999",
            option=option,
        )


async def _seed_person(session) -> tuple[str, int]:
    async with session.begin():
        unit = Unit(name="Persistence Unit", normal_overlap_limit=2)
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

        person = Personnel(full_name="Persistence User", role=UserRole.PERSONNEL, unit_id=unit.id)
        session.add(person)
        await session.flush()
        return str(person.id), policy.id

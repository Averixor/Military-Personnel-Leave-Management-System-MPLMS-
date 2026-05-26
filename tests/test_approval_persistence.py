from datetime import date

import pytest
from sqlalchemy import select

from mplms.domain.enums import LeaveType
from mplms.domain.enums import RequestStatus
from mplms.domain.enums import UserRole
from mplms.models.personnel import Personnel
from mplms.models.personnel import Unit
from mplms.models.policy import PolicySnapshot
from mplms.models.workflow import ApprovalStep
from mplms.models.workflow import LeaveRequest
from mplms.services.approval_persistence import approve_by_commander
from mplms.services.approval_persistence import mark_applied
from mplms.services.approval_persistence import mark_ready_to_apply
from mplms.services.approval_persistence import submit_selected_request_for_approval
from mplms.services.leave_request_persistence import create_persisted_leave_request
from mplms.services.leave_request_persistence import select_persisted_leave_option


@pytest.mark.asyncio
async def test_selected_request_can_be_submitted_for_approval(db_session) -> None:
    person_id, request_id = await _create_selected_request(db_session)

    updated = await submit_selected_request_for_approval(db_session, request_id=request_id)

    assert updated.status == RequestStatus.WAITING_COMMANDER_APPROVAL


@pytest.mark.asyncio
async def test_wrong_status_cannot_be_submitted(db_session) -> None:
    person_id, _ = await _seed_person(db_session)

    created = await create_persisted_leave_request(
        db_session,
        personnel_id=person_id,
        desired_start=date(2026, 6, 15),
        duration_days=5,
        leave_type=LeaveType.ANNUAL_MAIN.value,
        max_shift_days=0,
    )

    with pytest.raises(ValueError, match="selected_by_user"):
        await submit_selected_request_for_approval(db_session, request_id=created.request_id)


@pytest.mark.asyncio
async def test_commander_approval_changes_status_and_writes_commander_id(db_session) -> None:
    person_id, request_id = await _create_selected_request(db_session)
    commander_id = await _seed_commander(db_session)

    await submit_selected_request_for_approval(db_session, request_id=request_id)
    updated = await approve_by_commander(
        db_session,
        request_id=request_id,
        commander_id=commander_id,
    )

    assert updated.status == RequestStatus.APPROVED_BY_COMMANDER

    async with db_session.begin():
        steps = (
            await db_session.execute(
                select(ApprovalStep).where(ApprovalStep.request_id == int(request_id))
            )
        ).scalars().all()
        assert len(steps) == 1
        assert steps[0].approver_id == int(commander_id)
        assert steps[0].status == "approved"
        assert steps[0].decided_at is not None


@pytest.mark.asyncio
async def test_mark_ready_to_apply_only_after_commander_approval(db_session) -> None:
    person_id, request_id = await _create_selected_request(db_session)

    with pytest.raises(ValueError, match="approved_by_commander"):
        await mark_ready_to_apply(db_session, request_id=request_id)

    await submit_selected_request_for_approval(db_session, request_id=request_id)
    commander_id = await _seed_commander(db_session)
    await approve_by_commander(
        db_session,
        request_id=request_id,
        commander_id=commander_id,
    )

    updated = await mark_ready_to_apply(db_session, request_id=request_id)
    assert updated.status == RequestStatus.READY_TO_APPLY


@pytest.mark.asyncio
async def test_mark_applied_only_after_ready_to_apply(db_session) -> None:
    person_id, request_id = await _create_selected_request(db_session)

    with pytest.raises(ValueError, match="ready_to_apply"):
        await mark_applied(db_session, request_id=request_id)

    await _advance_to_ready_to_apply(db_session, request_id)
    updated = await mark_applied(db_session, request_id=request_id)
    assert updated.status == RequestStatus.APPLIED


@pytest.mark.asyncio
async def test_mark_applied_requires_selected_leave_period_id(db_session) -> None:
    person_id, policy_id = await _seed_person(db_session)

    async with db_session.begin():
        request = LeaveRequest(
            person_id=int(person_id),
            desired_start_date=date(2026, 6, 15),
            desired_days_count=5,
            status=RequestStatus.READY_TO_APPLY,
            policy_snapshot_id=policy_id,
            selected_leave_period_id=None,
        )
        db_session.add(request)
        await db_session.flush()
        request_id = str(request.id)

    with pytest.raises(ValueError, match="selected_leave_period_id"):
        await mark_applied(db_session, request_id=request_id)


@pytest.mark.asyncio
async def test_invalid_request_id_raises(db_session) -> None:
    with pytest.raises(ValueError, match="not found"):
        await submit_selected_request_for_approval(db_session, request_id="99999")


@pytest.mark.asyncio
async def test_full_approval_flow(db_session) -> None:
    person_id, request_id = await _create_selected_request(db_session)
    commander_id = await _seed_commander(db_session)

    await submit_selected_request_for_approval(db_session, request_id=request_id)
    await approve_by_commander(
        db_session,
        request_id=request_id,
        commander_id=commander_id,
    )
    await mark_ready_to_apply(db_session, request_id=request_id)
    final = await mark_applied(db_session, request_id=request_id)

    assert final.status == RequestStatus.APPLIED


async def _create_selected_request(session) -> tuple[str, str]:
    person_id, _policy_id = await _seed_person(session)
    created = await create_persisted_leave_request(
        session,
        personnel_id=person_id,
        desired_start=date(2026, 6, 15),
        duration_days=5,
        leave_type=LeaveType.ANNUAL_MAIN.value,
        max_shift_days=0,
    )
    await select_persisted_leave_option(
        session,
        request_id=created.request_id,
        option=created.options[0],
    )
    return person_id, created.request_id


async def _advance_to_ready_to_apply(session, request_id: str) -> None:
    commander_id = await _seed_commander(session)
    await submit_selected_request_for_approval(session, request_id=request_id)
    await approve_by_commander(
        session,
        request_id=request_id,
        commander_id=commander_id,
    )
    await mark_ready_to_apply(session, request_id=request_id)


async def _seed_person(session) -> tuple[str, int]:
    async with session.begin():
        unit = Unit(name="Approval Unit", normal_overlap_limit=2)
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

        person = Personnel(full_name="Approval Applicant", role=UserRole.PERSONNEL, unit_id=unit.id)
        session.add(person)
        await session.flush()
        return str(person.id), policy.id


async def _seed_commander(session) -> str:
    async with session.begin():
        unit = Unit(name="Commander Unit", normal_overlap_limit=2)
        session.add(unit)
        await session.flush()

        commander = Personnel(
            full_name="Unit Commander",
            role=UserRole.COMMANDER,
            unit_id=unit.id,
        )
        session.add(commander)
        await session.flush()
        return str(commander.id)

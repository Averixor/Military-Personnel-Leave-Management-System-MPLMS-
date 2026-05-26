from datetime import date

import pytest
from sqlalchemy import func
from sqlalchemy import select

from mplms.domain.enums import LeaveType
from mplms.domain.enums import RequestStatus
from mplms.domain.enums import UserRole
from mplms.models.audit import AuditLog
from mplms.models.personnel import Personnel
from mplms.models.personnel import Unit
from mplms.models.policy import PolicySnapshot
from mplms.services.approval_persistence import approve_by_commander
from mplms.services.approval_persistence import mark_applied
from mplms.services.approval_persistence import mark_ready_to_apply
from mplms.services.approval_persistence import submit_selected_request_for_approval
from mplms.services.audit import create_audit_log
from mplms.services.leave_request_persistence import create_persisted_leave_request
from mplms.services.leave_request_persistence import select_persisted_leave_option


@pytest.mark.asyncio
async def test_create_audit_log_creates_row(db_session) -> None:
    async with db_session.begin():
        log = await create_audit_log(
            db_session,
            entity_type="leave_request",
            entity_id="1",
            operation="test_operation",
            changed_by="42",
            old_values={"status": "draft"},
            new_values={"status": "options_generated"},
            reason="Test audit entry",
        )

    async with db_session.begin():
        row = await db_session.get(AuditLog, log.id)
        assert row is not None
        assert row.action == "test_operation"
        assert row.entity_type == "leave_request"
        assert row.entity_id == 1
        assert row.actor_id == 42
        assert row.before_state == {"status": "draft"}
        assert row.after_state == {"status": "options_generated"}
        assert row.reason == "Test audit entry"


@pytest.mark.asyncio
async def test_create_request_writes_audit_row(db_session) -> None:
    person_id, _ = await _seed_person(db_session)

    created = await create_persisted_leave_request(
        db_session,
        personnel_id=person_id,
        desired_start=date(2026, 6, 15),
        duration_days=5,
        leave_type=LeaveType.ANNUAL_MAIN.value,
        max_shift_days=0,
    )

    count = await _audit_count(db_session, created.request_id, "leave_request_created")
    assert count == 1


@pytest.mark.asyncio
async def test_select_option_writes_audit_row(db_session) -> None:
    person_id, request_id = await _create_selected_request(db_session)

    count = await _audit_count(db_session, request_id, "leave_option_selected")
    assert count == 1

    async with db_session.begin():
        log = (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.entity_id == int(request_id),
                    AuditLog.action == "leave_option_selected",
                )
            )
        ).scalar_one()
        assert log.actor_id == int(person_id)
        assert log.before_state == {"status": RequestStatus.OPTIONS_GENERATED.value}
        assert log.after_state == {"status": RequestStatus.SELECTED_BY_USER.value}


@pytest.mark.asyncio
async def test_submit_approval_writes_audit_row(db_session) -> None:
    _person_id, request_id = await _create_selected_request(db_session)

    await submit_selected_request_for_approval(db_session, request_id=request_id)

    count = await _audit_count(db_session, request_id, "submitted_for_approval")
    assert count == 1


@pytest.mark.asyncio
async def test_commander_approval_writes_audit_with_commander_id(db_session) -> None:
    _person_id, request_id = await _create_selected_request(db_session)
    commander_id = await _seed_commander(db_session)

    await submit_selected_request_for_approval(db_session, request_id=request_id)
    await approve_by_commander(
        db_session,
        request_id=request_id,
        commander_id=commander_id,
    )

    async with db_session.begin():
        log = (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.entity_id == int(request_id),
                    AuditLog.action == "commander_approved",
                )
            )
        ).scalar_one()
        assert log.actor_id == int(commander_id)
        assert log.before_state == {"status": RequestStatus.WAITING_COMMANDER_APPROVAL.value}
        assert log.after_state == {"status": RequestStatus.APPROVED_BY_COMMANDER.value}


@pytest.mark.asyncio
async def test_mark_applied_writes_audit_row(db_session) -> None:
    _person_id, request_id = await _create_selected_request(db_session)
    commander_id = await _seed_commander(db_session)

    await submit_selected_request_for_approval(db_session, request_id=request_id)
    await approve_by_commander(
        db_session,
        request_id=request_id,
        commander_id=commander_id,
    )
    await mark_ready_to_apply(db_session, request_id=request_id)
    await mark_applied(db_session, request_id=request_id)

    count = await _audit_count(db_session, request_id, "applied")
    assert count == 1


async def _audit_count(session, request_id: str, action: str) -> int:
    async with session.begin():
        return await session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.entity_type == "leave_request",
                AuditLog.entity_id == int(request_id),
                AuditLog.action == action,
            )
        )


async def _create_selected_request(session) -> tuple[str, str]:
    person_id, _ = await _seed_person(session)
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


async def _seed_person(session) -> tuple[str, int]:
    async with session.begin():
        unit = Unit(name="Audit Unit", normal_overlap_limit=2)
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

        person = Personnel(full_name="Audit Applicant", role=UserRole.PERSONNEL, unit_id=unit.id)
        session.add(person)
        await session.flush()
        return str(person.id), policy.id


async def _seed_commander(session) -> str:
    async with session.begin():
        unit = Unit(name="Audit Commander Unit", normal_overlap_limit=2)
        session.add(unit)
        await session.flush()

        commander = Personnel(
            full_name="Audit Commander",
            role=UserRole.COMMANDER,
            unit_id=unit.id,
        )
        session.add(commander)
        await session.flush()
        return str(commander.id)

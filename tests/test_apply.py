from datetime import date

import pytest
from sqlalchemy import func
from sqlalchemy import select

from mplms.domain.enums import LeaveStatus
from mplms.domain.enums import LeaveType
from mplms.domain.enums import RequestStatus
from mplms.models.audit import AuditLog
from mplms.models.audit import OverrideAudit
from mplms.models.leave import LeavePeriod
from mplms.models.workflow import LeaveRequest
from mplms.models.workflow import RequestOption
from mplms.services.apply import ApplyNotAllowedError
from mplms.services.apply import apply_request
from mplms.services.apply_validation import ApplyValidationError

from tests.conftest import requires_postgres

pytestmark = requires_postgres


@pytest.mark.asyncio
async def test_cannot_apply_draft_request(db_session, seeded_ready_request) -> None:
    request = await db_session.get(LeaveRequest, seeded_ready_request["request_id"])
    assert request is not None
    request.status = RequestStatus.DRAFT

    with pytest.raises(ApplyNotAllowedError):
        await apply_request(db_session, request.id, seeded_ready_request["admin_id"])


@pytest.mark.asyncio
async def test_cannot_double_apply(db_session, seeded_ready_request) -> None:
    await apply_request(
        db_session,
        seeded_ready_request["request_id"],
        seeded_ready_request["admin_id"],
    )

    with pytest.raises(ApplyNotAllowedError, match="already applied"):
        await apply_request(
            db_session,
            seeded_ready_request["request_id"],
            seeded_ready_request["admin_id"],
        )


@pytest.mark.asyncio
async def test_frozen_leave_blocks_apply(db_session, seeded_ready_request) -> None:
    leave = await db_session.get(LeavePeriod, seeded_ready_request["leave_id"])
    assert leave is not None
    leave.is_frozen = True

    with pytest.raises(ApplyValidationError, match="Frozen leave"):
        await apply_request(
            db_session,
            seeded_ready_request["request_id"],
            seeded_ready_request["admin_id"],
        )

    refreshed = await db_session.get(LeavePeriod, leave.id)
    request = await db_session.get(LeaveRequest, seeded_ready_request["request_id"])
    assert refreshed is not None and request is not None
    assert refreshed.starts_on == date(2026, 7, 1)
    assert request.status == RequestStatus.READY_TO_APPLY


@pytest.mark.asyncio
async def test_successful_apply_changes_leave_dates(db_session, seeded_ready_request) -> None:
    await apply_request(
        db_session,
        seeded_ready_request["request_id"],
        seeded_ready_request["admin_id"],
    )

    leave = await db_session.get(LeavePeriod, seeded_ready_request["leave_id"])
    request = await db_session.get(LeaveRequest, seeded_ready_request["request_id"])
    assert leave is not None and request is not None
    assert leave.starts_on == seeded_ready_request["new_start"]
    assert leave.ends_on == seeded_ready_request["new_end"]
    assert leave.days_count == 15
    assert leave.source_request_id == seeded_ready_request["request_id"]
    assert request.status == RequestStatus.APPLIED


@pytest.mark.asyncio
async def test_audit_log_created(db_session, seeded_ready_request) -> None:
    await apply_request(
        db_session,
        seeded_ready_request["request_id"],
        seeded_ready_request["admin_id"],
    )

    count = await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "apply_request",
            AuditLog.entity_type == "leave_request",
            AuditLog.entity_id == seeded_ready_request["request_id"],
        )
    )
    assert count == 1

    override_count = await db_session.scalar(select(func.count()).select_from(OverrideAudit))
    assert override_count == 0


@pytest.mark.asyncio
async def test_transaction_rollback_on_validation_failure(db_session, seeded_ready_request) -> None:
    request = await db_session.get(LeaveRequest, seeded_ready_request["request_id"])
    assert request is not None
    overlapping = LeavePeriod(
        person_id=seeded_ready_request["applicant_id"],
        leave_type=LeaveType.ANNUAL_SECOND_PART,
        year=2026,
        starts_on=date(2026, 8, 10),
        ends_on=date(2026, 8, 20),
        days_count=11,
        initial_starts_on=date(2026, 8, 10),
        initial_ends_on=date(2026, 8, 20),
        status=LeaveStatus.PLANNED,
        is_frozen=False,
        policy_snapshot_id=request.policy_snapshot_id,
    )
    db_session.add(overlapping)
    await db_session.flush()

    with pytest.raises(ApplyValidationError, match="Self-overlapping"):
        await apply_request(
            db_session,
            seeded_ready_request["request_id"],
            seeded_ready_request["admin_id"],
        )

    leave = await db_session.get(LeavePeriod, seeded_ready_request["leave_id"])
    request = await db_session.get(LeaveRequest, seeded_ready_request["request_id"])
    audit_count = await db_session.scalar(select(func.count()).select_from(AuditLog))

    assert leave is not None and request is not None
    assert leave.starts_on == date(2026, 7, 1)
    assert request.status == RequestStatus.READY_TO_APPLY
    assert audit_count == 0


@pytest.mark.asyncio
async def test_override_apply_creates_override_audit(db_session, seeded_ready_request) -> None:
    leave = await db_session.get(LeavePeriod, seeded_ready_request["leave_id"])
    option = await db_session.get(RequestOption, seeded_ready_request["option_id"])
    assert leave is not None and option is not None
    leave.is_frozen = True
    option.explanation = {
        **option.explanation,
        "override": True,
        "override_type": "hard",
        "override_reason": "super admin override for test",
    }

    await apply_request(
        db_session,
        seeded_ready_request["request_id"],
        seeded_ready_request["admin_id"],
    )

    override_count = await db_session.scalar(
        select(func.count())
        .select_from(OverrideAudit)
        .where(OverrideAudit.entity_id == seeded_ready_request["request_id"])
    )
    assert override_count == 1

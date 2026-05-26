from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mplms.domain.enums import RequestStatus
from mplms.models.audit import AuditLog
from mplms.models.audit import OverrideAudit
from mplms.models.conflict import ConflictGroup
from mplms.models.leave import LeavePeriod
from mplms.models.personnel import Personnel
from mplms.models.personnel import Unit
from mplms.models.workflow import LeaveRequest
from mplms.models.workflow import RequestOption
from mplms.services.apply_validation import ApplyValidationError
from mplms.services.apply_validation import LeaveChangePlan
from mplms.services.apply_validation import parse_leave_changes
from mplms.services.apply_validation import validate_conflict_groups
from mplms.services.apply_validation import validate_frozen_leaves
from mplms.services.apply_validation import validate_overlap_limits
from mplms.services.apply_validation import validate_selected_option_is_current
from mplms.services.apply_validation import validate_self_overlap
from mplms.services.apply_validation import validate_two_day_rule
from mplms.services.workflow import transition


class ApplyError(Exception):
    pass


class ApplyNotAllowedError(ApplyError):
    pass


async def apply_request(session: AsyncSession, request_id: int, admin_id: int) -> LeaveRequest:
    """Apply a ready_to_apply leave request inside a single database transaction."""
    async with session.begin():
        request = await _lock_request(session, request_id)
        _ensure_ready_to_apply(request)

        if request.selected_option_id is None:
            raise ApplyNotAllowedError("Request has no selected option")

        option = await _lock_option(session, request.selected_option_id)
        if option is None:
            raise ApplyValidationError("Selected option was not found")

        changes = parse_leave_changes(option.explanation)
        leave_ids = [change.leave_id for change in changes]
        leaves = await _lock_leaves(session, leave_ids)
        leaves_by_id = {leave.id: leave for leave in leaves}

        if set(leaves_by_id) != set(leave_ids):
            raise ApplyValidationError("One or more leave periods for apply are missing")

        override = bool(option.explanation.get("override", False))
        person_ids = {leave.person_id for leave in leaves}
        person_ids.add(request.person_id)

        admin = await session.get(Personnel, admin_id)
        if admin is None:
            raise ApplyNotAllowedError("Admin actor was not found")

        applicant = await session.get(Personnel, request.person_id)
        if applicant is None:
            raise ApplyValidationError("Request applicant was not found")

        unit = await session.get(Unit, applicant.unit_id) if applicant.unit_id else None
        unit_leaves = await _load_unit_leaves(session, applicant.unit_id) if applicant.unit_id else []
        person_leaves = await _load_person_leaves(session, person_ids)
        groups = await _load_conflict_groups(session)

        validate_selected_option_is_current(request, option)
        validate_frozen_leaves(leaves_by_id, changes, override=override)
        validate_two_day_rule(leaves_by_id, changes, override=override)

        for person_id, leaves_for_person in person_leaves.items():
            validate_self_overlap(leaves_for_person, changes)

        validate_overlap_limits(
            unit=unit,
            option=option,
            applicant=applicant,
            unit_leaves=unit_leaves,
            changes=changes,
            override=override,
        )
        validate_conflict_groups(
            groups=groups,
            applicant_id=request.person_id,
            option=option,
            person_leaves=person_leaves,
            changes=changes,
            override=override,
        )

        before_state = _request_state(request)
        leave_before = {leave.id: _leave_state(leave) for leave in leaves}

        for change in changes:
            leave = leaves_by_id[change.leave_id]
            leave.starts_on = change.starts_on
            leave.ends_on = change.ends_on
            leave.days_count = (change.ends_on - change.starts_on).days + 1
            leave.source_request_id = request.id

        request.status = transition(RequestStatus.READY_TO_APPLY, RequestStatus.APPLIED)

        session.add(
            AuditLog(
                actor_id=admin_id,
                actor_role=str(admin.role),
                action="apply_request",
                entity_type="leave_request",
                entity_id=request.id,
                before_state={
                    "request": before_state,
                    "leaves": leave_before,
                },
                after_state={
                    "request": _request_state(request),
                    "leaves": {leave.id: _leave_state(leave) for leave in leaves},
                },
            )
        )

        if override:
            session.add(
                OverrideAudit(
                    actor_id=admin_id,
                    override_type=str(option.explanation.get("override_type", "hard")),
                    action="apply_request",
                    entity_type="leave_request",
                    entity_id=request.id,
                    reason=str(option.explanation.get("override_reason", "override apply")),
                    payload=option.explanation,
                )
            )

        return request


def _ensure_ready_to_apply(request: LeaveRequest) -> None:
    if request.status == RequestStatus.APPLIED:
        raise ApplyNotAllowedError("Leave request was already applied")
    if request.status != RequestStatus.READY_TO_APPLY:
        raise ApplyNotAllowedError(
            f"Leave request must be ready_to_apply, got {request.status}"
        )


async def _lock_request(session: AsyncSession, request_id: int) -> LeaveRequest:
    stmt = select(LeaveRequest).where(LeaveRequest.id == request_id).with_for_update()
    result = await session.execute(stmt)
    request = result.scalar_one_or_none()
    if request is None:
        raise ApplyNotAllowedError(f"Leave request {request_id} was not found")
    return request


async def _lock_option(session: AsyncSession, option_id: int) -> RequestOption | None:
    stmt = select(RequestOption).where(RequestOption.id == option_id).with_for_update()
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _lock_leaves(session: AsyncSession, leave_ids: list[int]) -> list[LeavePeriod]:
    if not leave_ids:
        return []
    stmt = select(LeavePeriod).where(LeavePeriod.id.in_(leave_ids)).with_for_update()
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _load_unit_leaves(session: AsyncSession, unit_id: int) -> list[LeavePeriod]:
    stmt = (
        select(LeavePeriod)
        .join(Personnel, Personnel.id == LeavePeriod.person_id)
        .where(Personnel.unit_id == unit_id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _load_person_leaves(
    session: AsyncSession,
    person_ids: set[int],
) -> dict[int, list[LeavePeriod]]:
    if not person_ids:
        return {}
    stmt = select(LeavePeriod).where(LeavePeriod.person_id.in_(person_ids))
    result = await session.execute(stmt)
    grouped: dict[int, list[LeavePeriod]] = {person_id: [] for person_id in person_ids}
    for leave in result.scalars().all():
        grouped.setdefault(leave.person_id, []).append(leave)
    return grouped


async def _load_conflict_groups(session: AsyncSession) -> list[ConflictGroup]:
    result = await session.execute(select(ConflictGroup))
    return list(result.scalars().all())


def _request_state(request: LeaveRequest) -> dict:
    return {
        "id": request.id,
        "status": str(request.status),
        "selected_option_id": request.selected_option_id,
        "person_id": request.person_id,
    }


def _leave_state(leave: LeavePeriod) -> dict:
    return {
        "id": leave.id,
        "person_id": leave.person_id,
        "starts_on": leave.starts_on.isoformat(),
        "ends_on": leave.ends_on.isoformat(),
        "days_count": leave.days_count,
        "is_frozen": leave.is_frozen,
        "source_request_id": leave.source_request_id,
    }


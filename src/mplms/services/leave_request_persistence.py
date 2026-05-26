"""Persist leave request drafts using SQLAlchemy models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mplms.domain.enums import LeaveStatus
from mplms.domain.enums import LeaveType
from mplms.domain.enums import RequestStatus
from mplms.models.leave import LeavePeriod
from mplms.models.personnel import Personnel
from mplms.models.policy import PolicySnapshot
from mplms.models.workflow import LeaveRequest
from mplms.services.leave_request import STATUS_MANUAL_REVIEW_REQUIRED
from mplms.services.leave_request import STATUS_OPTIONS_GENERATED
from mplms.services.leave_request import STATUS_SELECTED_BY_USER
from mplms.services.leave_request import create_leave_request_draft
from mplms.services.scheduler import ExistingLeavePeriod
from mplms.services.scheduler import ScheduleOption

_DRAFT_TO_REQUEST_STATUS: dict[str, RequestStatus] = {
    STATUS_OPTIONS_GENERATED: RequestStatus.OPTIONS_GENERATED,
    STATUS_MANUAL_REVIEW_REQUIRED: RequestStatus.MANUAL_ADMIN_REVIEW_REQUIRED,
    STATUS_SELECTED_BY_USER: RequestStatus.SELECTED_BY_USER,
}


@dataclass(frozen=True)
class PersistedLeaveRequest:
    request_id: str
    personnel_id: str
    status: str
    options: tuple[ScheduleOption, ...]


async def create_persisted_leave_request(
    session: AsyncSession,
    personnel_id: str,
    desired_start: date,
    duration_days: int,
    leave_type: str,
    max_options: int = 10,
    max_shift_days: int = 14,
    normal_absence_limit: int = 2,
) -> PersistedLeaveRequest:
    person_pk = _parse_personnel_id(personnel_id)

    async with session.begin():
        await _ensure_personnel(session, person_pk)
        existing_periods = await _load_existing_periods(session, person_pk)
        draft = create_leave_request_draft(
            personnel_id=personnel_id,
            desired_start=desired_start,
            duration_days=duration_days,
            leave_type=leave_type,
            existing_periods=existing_periods,
            max_options=max_options,
            max_shift_days=max_shift_days,
            normal_absence_limit=normal_absence_limit,
        )
        policy = await _get_active_policy(session)
        LeaveType(leave_type)

        request = LeaveRequest(
            person_id=person_pk,
            desired_start_date=desired_start,
            desired_days_count=duration_days,
            status=_DRAFT_TO_REQUEST_STATUS[draft.status],
            policy_snapshot_id=policy.id,
        )
        session.add(request)
        await session.flush()

        return PersistedLeaveRequest(
            request_id=str(request.id),
            personnel_id=personnel_id,
            status=draft.status,
            options=draft.options,
        )


async def select_persisted_leave_option(
    session: AsyncSession,
    request_id: str,
    option: ScheduleOption,
) -> LeaveRequest:
    request_pk = _parse_request_id(request_id)

    async with session.begin():
        request = await session.get(LeaveRequest, request_pk)
        if request is None:
            raise ValueError(f"Leave request {request_id} was not found")

        if request.status != RequestStatus.OPTIONS_GENERATED:
            raise ValueError(
                f"Leave request {request_id} must be in options_generated status, "
                f"got {request.status}"
            )

        leave_type = await _resolve_leave_type_for_request(session, request)
        leave_period = LeavePeriod(
            person_id=request.person_id,
            leave_type=leave_type,
            year=option.start_date.year,
            starts_on=option.start_date,
            ends_on=option.end_date,
            days_count=option.duration_days,
            initial_starts_on=option.start_date,
            initial_ends_on=option.end_date,
            status=LeaveStatus.PLANNED,
            is_frozen=False,
            policy_snapshot_id=request.policy_snapshot_id,
            source_request_id=request.id,
        )
        session.add(leave_period)
        await session.flush()

        request.status = RequestStatus.SELECTED_BY_USER
        await session.flush()

        return request


def _parse_personnel_id(personnel_id: str) -> int:
    try:
        return int(personnel_id)
    except ValueError as exc:
        raise ValueError(f"Invalid personnel_id: {personnel_id!r}") from exc


def _parse_request_id(request_id: str) -> int:
    try:
        return int(request_id)
    except ValueError as exc:
        raise ValueError(f"Invalid request_id: {request_id!r}") from exc


async def _ensure_personnel(session: AsyncSession, person_pk: int) -> Personnel:
    person = await session.get(Personnel, person_pk)
    if person is None:
        raise ValueError(f"Personnel {person_pk} was not found")
    return person


async def _load_existing_periods(session: AsyncSession, person_pk: int) -> list[ExistingLeavePeriod]:
    result = await session.execute(
        select(LeavePeriod).where(LeavePeriod.person_id == person_pk)
    )
    return [
        ExistingLeavePeriod(start_date=period.starts_on, end_date=period.ends_on)
        for period in result.scalars().all()
    ]


async def _get_active_policy(session: AsyncSession) -> PolicySnapshot:
    result = await session.execute(
        select(PolicySnapshot).where(PolicySnapshot.is_active.is_(True)).limit(1)
    )
    policy = result.scalar_one_or_none()
    if policy is None:
        raise ValueError("No active policy snapshot found")
    return policy


async def _resolve_leave_type_for_request(session: AsyncSession, request: LeaveRequest) -> LeaveType:
    result = await session.execute(
        select(LeavePeriod)
        .where(LeavePeriod.person_id == request.person_id)
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing.leave_type
    return LeaveType.ANNUAL_MAIN

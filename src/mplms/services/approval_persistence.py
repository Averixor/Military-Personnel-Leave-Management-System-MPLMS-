"""Persist approval workflow transitions for leave requests."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mplms.domain.enums import RequestStatus
from mplms.domain.enums import UserRole
from mplms.models.leave import LeavePeriod
from mplms.models.workflow import ApprovalStep
from mplms.models.workflow import LeaveRequest
from mplms.services.audit import create_audit_log
from mplms.services.audit import status_str
from mplms.services.workflow import transition


async def submit_selected_request_for_approval(
    session: AsyncSession,
    request_id: str,
) -> LeaveRequest:
    request_pk = _parse_request_id(request_id)

    async with session.begin():
        request = await _get_request(session, request_pk, request_id)
        if request.status != RequestStatus.SELECTED_BY_USER:
            raise ValueError(
                f"Leave request {request_id} must be in selected_by_user status, "
                f"got {request.status}"
            )

        old_status = status_str(request.status)
        request.status = transition(
            RequestStatus.SELECTED_BY_USER,
            RequestStatus.WAITING_COMMANDER_APPROVAL,
        )
        await session.flush()

        await create_audit_log(
            session,
            entity_type="leave_request",
            entity_id=str(request.id),
            operation="submitted_for_approval",
            changed_by=str(request.person_id),
            old_values={"status": old_status},
            new_values={"status": status_str(request.status)},
            reason="Leave request submitted for commander approval",
        )
        return request


async def approve_by_commander(
    session: AsyncSession,
    request_id: str,
    commander_id: str,
) -> LeaveRequest:
    request_pk = _parse_request_id(request_id)
    commander_pk = _parse_personnel_id(commander_id)

    async with session.begin():
        request = await _get_request(session, request_pk, request_id)
        if request.status != RequestStatus.WAITING_COMMANDER_APPROVAL:
            raise ValueError(
                f"Leave request {request_id} must be in waiting_commander_approval status, "
                f"got {request.status}"
            )

        old_status = status_str(request.status)
        request.status = transition(
            RequestStatus.WAITING_COMMANDER_APPROVAL,
            RequestStatus.APPROVED_BY_COMMANDER,
        )
        session.add(
            ApprovalStep(
                request_id=request.id,
                approver_id=commander_pk,
                role=UserRole.COMMANDER.value,
                status="approved",
                decided_at=datetime.now(timezone.utc),
            )
        )
        await session.flush()

        await create_audit_log(
            session,
            entity_type="leave_request",
            entity_id=str(request.id),
            operation="commander_approved",
            changed_by=commander_id,
            old_values={"status": old_status},
            new_values={"status": status_str(request.status)},
            reason="Commander approved leave request",
        )
        return request


async def mark_ready_to_apply(
    session: AsyncSession,
    request_id: str,
) -> LeaveRequest:
    request_pk = _parse_request_id(request_id)

    async with session.begin():
        request = await _get_request(session, request_pk, request_id)
        if request.status != RequestStatus.APPROVED_BY_COMMANDER:
            raise ValueError(
                f"Leave request {request_id} must be in approved_by_commander status, "
                f"got {request.status}"
            )

        old_status = status_str(request.status)
        request.status = transition(
            RequestStatus.APPROVED_BY_COMMANDER,
            RequestStatus.READY_TO_APPLY,
        )
        await session.flush()

        await create_audit_log(
            session,
            entity_type="leave_request",
            entity_id=str(request.id),
            operation="ready_to_apply",
            old_values={"status": old_status},
            new_values={"status": status_str(request.status)},
            reason="Leave request marked ready to apply",
        )
        return request


async def mark_applied(
    session: AsyncSession,
    request_id: str,
) -> LeaveRequest:
    request_pk = _parse_request_id(request_id)

    async with session.begin():
        request = await _get_request(session, request_pk, request_id)
        if request.status != RequestStatus.READY_TO_APPLY:
            raise ValueError(
                f"Leave request {request_id} must be in ready_to_apply status, "
                f"got {request.status}"
            )

        if request.selected_leave_period_id is None:
            raise ValueError(
                f"Leave request {request_id} has no selected_leave_period_id"
            )

        leave_period = await session.get(LeavePeriod, request.selected_leave_period_id)
        if leave_period is None:
            raise ValueError(
                f"Selected leave period {request.selected_leave_period_id} was not found"
            )

        old_status = status_str(request.status)
        request.status = transition(
            RequestStatus.READY_TO_APPLY,
            RequestStatus.APPLIED,
        )
        await session.flush()

        await create_audit_log(
            session,
            entity_type="leave_request",
            entity_id=str(request.id),
            operation="applied",
            old_values={"status": old_status},
            new_values={"status": status_str(request.status)},
            reason="Leave request marked as applied",
        )
        return request


def _parse_request_id(request_id: str) -> int:
    try:
        return int(request_id)
    except ValueError as exc:
        raise ValueError(f"Invalid request_id: {request_id!r}") from exc


def _parse_personnel_id(personnel_id: str) -> int:
    try:
        return int(personnel_id)
    except ValueError as exc:
        raise ValueError(f"Invalid personnel_id: {personnel_id!r}") from exc


async def _get_request(session: AsyncSession, request_pk: int, request_id: str) -> LeaveRequest:
    request = await session.get(LeaveRequest, request_pk)
    if request is None:
        raise ValueError(f"Leave request {request_id} was not found")
    return request

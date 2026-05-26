"""Leave request draft lifecycle (in-memory MVP; no database)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from dataclasses import replace
from datetime import date
from uuid import uuid4

from mplms.services.scheduler import ExistingLeavePeriod
from mplms.services.scheduler import ScheduleOption
from mplms.services.scheduler import find_leave_options

STATUS_OPTIONS_GENERATED = "options_generated"
STATUS_MANUAL_REVIEW_REQUIRED = "manual_review_required"
STATUS_SELECTED_BY_USER = "selected_by_user"


@dataclass(frozen=True)
class LeaveRequestDraft:
    request_id: str
    personnel_id: str
    desired_start: date
    duration_days: int
    leave_type: str
    options: tuple[ScheduleOption, ...]
    status: str
    selected_option: ScheduleOption | None = None


def create_leave_request_draft(
    personnel_id: str,
    desired_start: date,
    duration_days: int,
    leave_type: str,
    existing_periods: Iterable[ExistingLeavePeriod | object],
    max_options: int = 10,
    max_shift_days: int = 14,
    normal_absence_limit: int = 2,
) -> LeaveRequestDraft:
    if duration_days <= 0:
        raise ValueError("duration_days must be greater than 0")
    if max_options <= 0:
        raise ValueError("max_options must be greater than 0")

    options = find_leave_options(
        desired_start=desired_start,
        duration_days=duration_days,
        existing_periods=existing_periods,
        max_options=max_options,
        max_shift_days=max_shift_days,
        normal_absence_limit=normal_absence_limit,
    )

    if not options:
        return LeaveRequestDraft(
            request_id=str(uuid4()),
            personnel_id=personnel_id,
            desired_start=desired_start,
            duration_days=duration_days,
            leave_type=leave_type,
            options=(),
            selected_option=None,
            status=STATUS_MANUAL_REVIEW_REQUIRED,
        )

    return LeaveRequestDraft(
        request_id=str(uuid4()),
        personnel_id=personnel_id,
        desired_start=desired_start,
        duration_days=duration_days,
        leave_type=leave_type,
        options=tuple(options),
        selected_option=None,
        status=STATUS_OPTIONS_GENERATED,
    )


def select_leave_option(draft: LeaveRequestDraft, option_index: int) -> LeaveRequestDraft:
    if draft.status != STATUS_OPTIONS_GENERATED:
        raise ValueError(
            f"Cannot select option when status is {draft.status!r}; "
            f"expected {STATUS_OPTIONS_GENERATED!r}"
        )
    if option_index < 0 or option_index >= len(draft.options):
        raise IndexError(f"option_index {option_index} out of range for {len(draft.options)} options")

    return replace(
        draft,
        selected_option=draft.options[option_index],
        status=STATUS_SELECTED_BY_USER,
    )

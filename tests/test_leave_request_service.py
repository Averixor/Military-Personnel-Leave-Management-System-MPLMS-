from datetime import date

import pytest

from mplms.services.leave_request import STATUS_MANUAL_REVIEW_REQUIRED
from mplms.services.leave_request import STATUS_OPTIONS_GENERATED
from mplms.services.leave_request import STATUS_SELECTED_BY_USER
from mplms.services.leave_request import create_leave_request_draft
from mplms.services.leave_request import select_leave_option
from mplms.services.scheduler import ExistingLeavePeriod


def test_create_draft_generates_options() -> None:
    draft = create_leave_request_draft(
        personnel_id="p-1",
        desired_start=date(2026, 6, 15),
        duration_days=10,
        leave_type="annual_main",
        existing_periods=[],
        max_shift_days=3,
    )
    assert draft.status == STATUS_OPTIONS_GENERATED
    assert len(draft.options) > 0
    assert draft.request_id
    assert draft.selected_option is None


def test_desired_date_first_when_no_conflicts() -> None:
    desired = date(2026, 6, 15)
    draft = create_leave_request_draft(
        personnel_id="p-1",
        desired_start=desired,
        duration_days=5,
        leave_type="annual_main",
        existing_periods=[],
        max_shift_days=2,
    )
    assert draft.options[0].start_date == desired
    assert draft.options[0].conflict_score == 0


def test_invalid_duration_raises_value_error() -> None:
    with pytest.raises(ValueError, match="duration_days"):
        create_leave_request_draft(
            personnel_id="p-1",
            desired_start=date(2026, 6, 15),
            duration_days=0,
            leave_type="annual_main",
            existing_periods=[],
        )


def test_no_options_leads_to_manual_review_required() -> None:
    existing = [
        ExistingLeavePeriod(date(2026, 6, 14), date(2026, 6, 16)),
        ExistingLeavePeriod(date(2026, 6, 14), date(2026, 6, 16)),
        ExistingLeavePeriod(date(2026, 6, 14), date(2026, 6, 16)),
        ExistingLeavePeriod(date(2026, 6, 14), date(2026, 6, 16)),
        ExistingLeavePeriod(date(2026, 6, 14), date(2026, 6, 16)),
    ]
    draft = create_leave_request_draft(
        personnel_id="p-1",
        desired_start=date(2026, 6, 15),
        duration_days=3,
        leave_type="annual_main",
        existing_periods=existing,
        max_shift_days=0,
        normal_absence_limit=2,
    )
    assert draft.status == STATUS_MANUAL_REVIEW_REQUIRED
    assert draft.options == ()


def test_select_valid_option_sets_selected_by_user() -> None:
    draft = create_leave_request_draft(
        personnel_id="p-1",
        desired_start=date(2026, 6, 15),
        duration_days=5,
        leave_type="annual_main",
        existing_periods=[],
        max_shift_days=1,
    )
    updated = select_leave_option(draft, 0)
    assert updated.status == STATUS_SELECTED_BY_USER
    assert updated.selected_option == draft.options[0]


def test_select_invalid_index_raises() -> None:
    draft = create_leave_request_draft(
        personnel_id="p-1",
        desired_start=date(2026, 6, 15),
        duration_days=5,
        leave_type="annual_main",
        existing_periods=[],
        max_shift_days=0,
    )
    with pytest.raises(IndexError):
        select_leave_option(draft, 99)


def test_select_does_not_mutate_original_draft() -> None:
    draft = create_leave_request_draft(
        personnel_id="p-1",
        desired_start=date(2026, 6, 15),
        duration_days=5,
        leave_type="annual_main",
        existing_periods=[],
        max_shift_days=0,
    )
    original_status = draft.status
    original_selected = draft.selected_option
    _ = select_leave_option(draft, 0)
    assert draft.status == original_status
    assert draft.selected_option is original_selected

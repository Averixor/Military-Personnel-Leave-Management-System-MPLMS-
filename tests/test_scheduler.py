from datetime import date

from mplms.services.scheduler import ExistingLeavePeriod
from mplms.services.scheduler import find_leave_options


def test_no_existing_leaves_prefers_desired_start() -> None:
    desired = date(2026, 6, 15)
    options = find_leave_options(
        desired_start=desired,
        duration_days=15,
        existing_periods=[],
        max_shift_days=3,
    )
    assert options
    assert options[0].start_date == desired
    assert options[0].conflict_score == 0
    assert options[0].overlap_count == 0


def test_overlapping_leave_increases_conflict_score() -> None:
    desired = date(2026, 6, 15)
    existing = [
        ExistingLeavePeriod(
            start_date=date(2026, 6, 10),
            end_date=date(2026, 6, 20),
        )
    ]
    options = find_leave_options(
        desired_start=desired,
        duration_days=10,
        existing_periods=existing,
        max_shift_days=0,
    )
    assert len(options) == 1
    assert options[0].overlap_count == 1
    assert options[0].conflict_score > 0


def test_equal_score_prefers_closer_to_desired_start() -> None:
    desired = date(2026, 6, 15)
    options = find_leave_options(
        desired_start=desired,
        duration_days=5,
        existing_periods=[],
        max_shift_days=2,
        max_options=10,
    )
    scores = {option.conflict_score for option in options}
    assert len(scores) == 1
    assert options[0].start_date == desired
    # Same score: closer offsets first; ties broken by earlier calendar date.
    assert [option.start_date for option in options[:3]] == [
        date(2026, 6, 15),
        date(2026, 6, 14),
        date(2026, 6, 16),
    ]


def test_forbidden_when_peak_absence_exceeds_limit_plus_three() -> None:
    desired = date(2026, 6, 15)
    existing = [
        ExistingLeavePeriod(date(2026, 6, 14), date(2026, 6, 16)),
        ExistingLeavePeriod(date(2026, 6, 14), date(2026, 6, 16)),
        ExistingLeavePeriod(date(2026, 6, 14), date(2026, 6, 16)),
        ExistingLeavePeriod(date(2026, 6, 14), date(2026, 6, 16)),
        ExistingLeavePeriod(date(2026, 6, 14), date(2026, 6, 16)),
    ]
    options = find_leave_options(
        desired_start=desired,
        duration_days=3,
        existing_periods=existing,
        max_shift_days=0,
        normal_absence_limit=2,
    )
    assert options == []


def test_respects_max_options() -> None:
    desired = date(2026, 6, 15)
    options = find_leave_options(
        desired_start=desired,
        duration_days=5,
        existing_periods=[],
        max_shift_days=20,
        max_options=5,
    )
    assert len(options) == 5


def test_duration_days_sets_end_date() -> None:
    start = date(2026, 6, 1)
    options = find_leave_options(
        desired_start=start,
        duration_days=15,
        existing_periods=[],
        max_shift_days=0,
    )
    assert len(options) == 1
    assert options[0].start_date == start
    assert options[0].end_date == date(2026, 6, 15)
    assert options[0].duration_days == 15

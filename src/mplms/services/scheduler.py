"""Pure scheduling calculations (no database access)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from datetime import timedelta


@dataclass(frozen=True)
class ExistingLeavePeriod:
    start_date: date
    end_date: date


@dataclass(frozen=True)
class ScheduleOption:
    start_date: date
    end_date: date
    duration_days: int
    conflict_score: int
    overlap_count: int
    max_absent_on_any_day: int
    reasons: list[str]


def find_leave_options(
    desired_start: date,
    duration_days: int,
    existing_periods: Iterable[ExistingLeavePeriod | object],
    max_options: int = 10,
    max_shift_days: int = 14,
    normal_absence_limit: int = 2,
) -> list[ScheduleOption]:
    """Return ranked leave date options around desired_start within the shift window."""
    if duration_days < 1 or max_options < 1:
        return []

    periods = [_normalize_period(period) for period in existing_periods]
    forbidden_peak = normal_absence_limit + 3
    candidates: list[ScheduleOption] = []

    for offset in _shift_offsets(max_shift_days):
        start_date = desired_start + timedelta(days=offset)
        end_date = start_date + timedelta(days=duration_days - 1)
        overlap_count = _count_overlapping_periods(start_date, end_date, periods)
        max_absent = _peak_absence(start_date, end_date, periods)

        if max_absent > forbidden_peak:
            continue

        conflict_score, reasons = _score_option(
            overlap_count=overlap_count,
            max_absent=max_absent,
            normal_absence_limit=normal_absence_limit,
        )
        candidates.append(
            ScheduleOption(
                start_date=start_date,
                end_date=end_date,
                duration_days=duration_days,
                conflict_score=conflict_score,
                overlap_count=overlap_count,
                max_absent_on_any_day=max_absent,
                reasons=reasons,
            )
        )

    candidates.sort(
        key=lambda option: (
            option.conflict_score,
            abs((option.start_date - desired_start).days),
            option.start_date,
        )
    )
    return candidates[:max_options]


def _normalize_period(period: object) -> ExistingLeavePeriod:
    if isinstance(period, ExistingLeavePeriod):
        return period
    start = getattr(period, "start_date", None)
    end = getattr(period, "end_date", None)
    if start is None:
        start = getattr(period, "starts_on")
    if end is None:
        end = getattr(period, "ends_on")
    if start is None or end is None:
        raise TypeError("existing period must provide start/end dates")
    return ExistingLeavePeriod(start_date=start, end_date=end)


def _shift_offsets(max_shift_days: int) -> list[int]:
    return sorted(
        range(-max_shift_days, max_shift_days + 1),
        key=lambda value: (abs(value), value),
    )


def _count_overlapping_periods(
    start_date: date,
    end_date: date,
    periods: list[ExistingLeavePeriod],
) -> int:
    return sum(
        1
        for period in periods
        if period.start_date <= end_date and start_date <= period.end_date
    )


def _peak_absence(
    start_date: date,
    end_date: date,
    periods: list[ExistingLeavePeriod],
) -> int:
    daily_existing: dict[date, int] = {}
    for period in periods:
        for day in _iter_days(period.start_date, period.end_date):
            daily_existing[day] = daily_existing.get(day, 0) + 1

    peak = 0
    for day in _iter_days(start_date, end_date):
        peak = max(peak, daily_existing.get(day, 0) + 1)
    return peak


def _iter_days(start_date: date, end_date: date):
    day = start_date
    while day <= end_date:
        yield day
        day += timedelta(days=1)


def _score_option(
    *,
    overlap_count: int,
    max_absent: int,
    normal_absence_limit: int,
) -> tuple[int, list[str]]:
    excess = max(0, max_absent - normal_absence_limit)
    score = overlap_count * 100 + excess * 10
    reasons: list[str] = []
    if overlap_count:
        reasons.append(f"{overlap_count} overlapping leave period(s)")
    if excess:
        reasons.append(
            f"peak absence {max_absent} exceeds normal limit {normal_absence_limit} by {excess}"
        )
    if not reasons:
        reasons.append("no staffing conflicts")
    return score, reasons


# --- Legacy boundary (delegates to find_leave_options) ---


@dataclass(frozen=True)
class SchedulingPerson:
    id: int
    criticality_level: int


@dataclass(frozen=True)
class CandidateSlot:
    starts_on: date
    ends_on: date
    conflict_score: int
    affected_personnel_ids: tuple[int, ...]
    overlap_level: int
    risk_level: str


@dataclass(frozen=True)
class SchedulerLimits:
    max_slots: int = 10
    max_shift_days: int = 14


class SchedulerEngine:
    """Thin wrapper kept for older call sites; unit scheduling uses existing_periods only."""

    def find_acceptable_slots(
        self,
        person: SchedulingPerson,
        desired_date: date,
        days_count: int,
        limits: SchedulerLimits | None = None,
        existing_periods: Iterable[ExistingLeavePeriod | object] | None = None,
    ) -> list[CandidateSlot]:
        limits = limits or SchedulerLimits()
        options = find_leave_options(
            desired_start=desired_date,
            duration_days=days_count,
            existing_periods=existing_periods or [],
            max_options=limits.max_slots,
            max_shift_days=limits.max_shift_days,
        )
        criticality_penalty = person.criticality_level * 10
        return [
            CandidateSlot(
                starts_on=option.start_date,
                ends_on=option.end_date,
                conflict_score=option.conflict_score + criticality_penalty,
                affected_personnel_ids=(),
                overlap_level=option.overlap_count,
                risk_level="low" if option.conflict_score == 0 else "medium",
            )
            for option in options
        ]

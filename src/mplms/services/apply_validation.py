from dataclasses import dataclass
from datetime import date
from datetime import timedelta

from mplms.domain.enums import LeaveStatus
from mplms.models.conflict import ConflictGroup
from mplms.models.leave import LeavePeriod
from mplms.models.personnel import Personnel
from mplms.models.personnel import Unit
from mplms.models.workflow import LeaveRequest
from mplms.models.workflow import RequestOption
from mplms.services.policies import OverlapLimitPolicy
from mplms.services.policies import PolicyViolation
from mplms.services.policies import validate_shift_from_initial


@dataclass(frozen=True)
class LeaveChangePlan:
    leave_id: int
    starts_on: date
    ends_on: date


class ApplyValidationError(Exception):
    pass


def parse_leave_changes(explanation: dict) -> list[LeaveChangePlan]:
    raw_changes = explanation.get("leave_changes")
    if not raw_changes:
        raise ApplyValidationError("Selected option is missing leave_changes in explanation")

    plans: list[LeaveChangePlan] = []
    for item in raw_changes:
        try:
            leave_id = int(item["leave_id"])
            starts_on = date.fromisoformat(str(item["starts_on"]))
            ends_on = date.fromisoformat(str(item["ends_on"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ApplyValidationError("Invalid leave_changes entry in option explanation") from exc
        if ends_on < starts_on:
            raise ApplyValidationError("Leave change has ends_on before starts_on")
        plans.append(LeaveChangePlan(leave_id=leave_id, starts_on=starts_on, ends_on=ends_on))
    return plans


def validate_selected_option_is_current(request: LeaveRequest, option: RequestOption) -> None:
    if request.selected_option_id != option.id:
        raise ApplyValidationError("Selected option no longer matches the request")
    if option.request_id != request.id:
        raise ApplyValidationError("Selected option does not belong to this request")

    fingerprint = option.explanation.get("option_fingerprint")
    if fingerprint:
        if fingerprint.get("proposed_start_date") != option.proposed_start_date.isoformat():
            raise ApplyValidationError("Selected option dates are no longer current")
        if fingerprint.get("proposed_end_date") != option.proposed_end_date.isoformat():
            raise ApplyValidationError("Selected option dates are no longer current")
        if fingerprint.get("overlap_level") != option.overlap_level:
            raise ApplyValidationError("Selected option overlap level is no longer current")


def validate_frozen_leaves(
    leaves_by_id: dict[int, LeavePeriod],
    changes: list[LeaveChangePlan],
    *,
    override: bool,
) -> None:
    if override:
        return
    for change in changes:
        leave = leaves_by_id[change.leave_id]
        if not leave.is_frozen:
            continue
        if leave.starts_on != change.starts_on or leave.ends_on != change.ends_on:
            raise ApplyValidationError("Frozen leave cannot be changed without override")


def validate_two_day_rule(
    leaves_by_id: dict[int, LeavePeriod],
    changes: list[LeaveChangePlan],
    *,
    override: bool,
) -> None:
    if override:
        return
    for change in changes:
        leave = leaves_by_id[change.leave_id]
        if leave.starts_on == change.starts_on and leave.ends_on == change.ends_on:
            continue
        try:
            validate_shift_from_initial(leave.initial_starts_on, change.starts_on)
        except PolicyViolation as exc:
            raise ApplyValidationError(str(exc)) from exc


def _periods_overlap(start_a: date, end_a: date, start_b: date, end_b: date) -> bool:
    return start_a <= end_b and start_b <= end_a


def _projected_period(leave: LeavePeriod, changes: list[LeaveChangePlan]) -> tuple[date, date]:
    for change in changes:
        if change.leave_id == leave.id:
            return change.starts_on, change.ends_on
    return leave.starts_on, leave.ends_on


def validate_self_overlap(
    person_leaves: list[LeavePeriod],
    changes: list[LeaveChangePlan],
) -> None:
    for index, left in enumerate(person_leaves):
        left_start, left_end = _projected_period(left, changes)
        for right in person_leaves[index + 1 :]:
            right_start, right_end = _projected_period(right, changes)
            if left.id == right.id:
                continue
            if _periods_overlap(left_start, left_end, right_start, right_end):
                raise ApplyValidationError("Self-overlapping leave periods are not allowed")


def _iter_dates(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _is_active_leave(leave: LeavePeriod) -> bool:
    return leave.status not in {LeaveStatus.CANCELLED}


def validate_overlap_limits(
    *,
    unit: Unit | None,
    option: RequestOption,
    applicant: Personnel,
    unit_leaves: list[LeavePeriod],
    changes: list[LeaveChangePlan],
    override: bool,
) -> None:
    if override:
        return
    if unit is None:
        return

    policy = OverlapLimitPolicy(normal_limit=unit.normal_overlap_limit)
    peak_absent = 0
    for day in _iter_dates(option.proposed_start_date, option.proposed_end_date):
        absent_count = 0
        for leave in unit_leaves:
            if leave.person_id == applicant.id:
                continue
            if not _is_active_leave(leave):
                continue
            start, end = _projected_period(leave, changes)
            if start <= day <= end:
                absent_count += 1
        peak_absent = max(peak_absent, absent_count)

    try:
        policy.max_consecutive_excess_days(peak_absent + 1)
    except PolicyViolation as exc:
        raise ApplyValidationError(str(exc)) from exc

    if option.overlap_level >= 4:
        raise ApplyValidationError("normal_limit +4 is forbidden")


def validate_conflict_groups(
    *,
    groups: list[ConflictGroup],
    applicant_id: int,
    option: RequestOption,
    person_leaves: dict[int, list[LeavePeriod]],
    changes: list[LeaveChangePlan],
    override: bool,
) -> None:
    if override:
        return

    for group in groups:
        members = {int(member_id) for member_id in group.member_personnel_ids}
        if applicant_id not in members:
            continue

        max_simultaneous = int(group.rules.get("max_simultaneous", 1))
        overlapping_members = 0
        for member_id in members:
            for leave in person_leaves.get(member_id, []):
                if not _is_active_leave(leave):
                    continue
                start, end = _projected_period(leave, changes)
                if _periods_overlap(
                    start,
                    end,
                    option.proposed_start_date,
                    option.proposed_end_date,
                ):
                    overlapping_members += 1
                    break

        if overlapping_members > max_simultaneous:
            raise ApplyValidationError(
                f"Conflict group '{group.name}' does not allow this overlap"
            )

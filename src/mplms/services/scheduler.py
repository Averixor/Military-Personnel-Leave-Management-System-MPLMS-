from dataclasses import dataclass
from datetime import date
from datetime import timedelta


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
    """Heuristic scheduler boundary.

    The first implementation intentionally favors a deterministic candidate pipeline
    over global optimization. Constraint-specific validators can be plugged into this
    boundary without coupling the Telegram UI to scheduling rules.
    """

    def find_acceptable_slots(
        self,
        person: SchedulingPerson,
        desired_date: date,
        days_count: int,
        limits: SchedulerLimits | None = None,
    ) -> list[CandidateSlot]:
        limits = limits or SchedulerLimits()
        candidates = self._build_date_window(desired_date, days_count, limits.max_shift_days)
        scored = [self._score_candidate(person, starts_on, days_count) for starts_on in candidates]
        scored.sort(key=lambda slot: (slot.conflict_score, slot.starts_on))
        return scored[: limits.max_slots]

    def _build_date_window(
        self,
        desired_date: date,
        days_count: int,
        max_shift_days: int,
    ) -> list[date]:
        offsets = sorted(range(-max_shift_days, max_shift_days + 1), key=lambda value: (abs(value), value))
        return [desired_date + timedelta(days=offset) for offset in offsets if days_count > 0]

    def _score_candidate(
        self,
        person: SchedulingPerson,
        starts_on: date,
        days_count: int,
    ) -> CandidateSlot:
        # Placeholder score. Real scoring will add overlap, hierarchy, shifts and frozen checks.
        ends_on = starts_on + timedelta(days=days_count - 1)
        criticality_penalty = person.criticality_level * 10
        return CandidateSlot(
            starts_on=starts_on,
            ends_on=ends_on,
            conflict_score=criticality_penalty,
            affected_personnel_ids=(),
            overlap_level=0,
            risk_level="low",
        )


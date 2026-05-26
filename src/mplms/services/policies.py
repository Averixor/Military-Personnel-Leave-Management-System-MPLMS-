from dataclasses import dataclass
from datetime import date
from datetime import timedelta

from mplms.domain.enums import CriticalityLevel


@dataclass(frozen=True)
class FreezePolicy:
    level_0_days: int = 20
    level_1_days: int = 20
    level_2_days: int = 25
    level_3_days: int = 30

    def days_for(self, criticality_level: CriticalityLevel) -> int:
        return {
            CriticalityLevel.NORMAL: self.level_0_days,
            CriticalityLevel.IMPORTANT: self.level_1_days,
            CriticalityLevel.CRITICAL: self.level_2_days,
            CriticalityLevel.STRATEGIC: self.level_3_days,
        }[criticality_level]

    def freeze_date_for(self, starts_on: date, criticality_level: CriticalityLevel) -> date:
        return starts_on - timedelta(days=self.days_for(criticality_level))


@dataclass(frozen=True)
class OverlapLimitPolicy:
    normal_limit: int

    def max_consecutive_excess_days(self, absent_count: int) -> int | None:
        excess = absent_count - self.normal_limit

        if excess <= 0:
            return None
        if excess == 1:
            return 12
        if excess == 2:
            return 8
        if excess == 3:
            return 4

        raise PolicyViolation("normal_limit +4 is forbidden")


class PolicyViolation(Exception):
    pass


def validate_shift_from_initial(initial: date, proposed: date, max_shift_days: int = 2) -> None:
    shift = abs((proposed - initial).days)
    if shift > max_shift_days:
        raise PolicyViolation("Leave cannot be shifted more than +/-2 days from initial date")


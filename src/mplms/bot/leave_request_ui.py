"""Presentation helpers for Telegram leave request flow."""

from __future__ import annotations

from datetime import date
from datetime import timedelta

from mplms.domain.enums import LeaveType
from mplms.services.scheduler import ScheduleOption

# MVP alias from product wording ("annual") to domain enum value.
LEAVE_TYPE_ANNUAL = LeaveType.ANNUAL_MAIN.value
REQUEST_DURATION_DAYS = 15
REQUEST_START_OFFSET_DAYS = 30
MAX_OPTIONS_TO_SHOW = 3


def default_desired_start(*, today: date | None = None) -> date:
    base = today or date.today()
    return base + timedelta(days=REQUEST_START_OFFSET_DAYS)


def format_option_line(index: int, option: ScheduleOption) -> str:
    return (
        f"{index + 1}. {option.start_date} — {option.end_date} "
        f"({option.duration_days} дн., score={option.conflict_score})"
    )


def format_options_message(request_id: str, options: tuple[ScheduleOption, ...]) -> str:
    shown = options[:MAX_OPTIONS_TO_SHOW]
    lines = [
        f"Заявка #{request_id} создана.",
        f"Желаемая дата начала: {default_desired_start()}",
        f"Длительность: {REQUEST_DURATION_DAYS} дн.",
        "",
        "Варианты (первые 3):",
    ]
    lines.extend(format_option_line(index, option) for index, option in enumerate(shown))
    lines.append("\nВыберите вариант кнопкой ниже.")
    return "\n".join(lines)


def format_selection_confirmation(option: ScheduleOption) -> str:
    return (
        "Вариант выбран.\n"
        f"Статус: selected_by_user\n"
        f"Даты: {option.start_date} — {option.end_date} ({option.duration_days} дн.)"
    )

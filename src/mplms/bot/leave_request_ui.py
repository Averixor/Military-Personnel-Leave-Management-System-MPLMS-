"""Presentation helpers for Telegram leave request flow."""

from __future__ import annotations

from datetime import date
from datetime import timedelta

from mplms.domain.enums import LeaveType
from mplms.domain.enums import RequestStatus
from mplms.models.leave import LeavePeriod
from mplms.models.workflow import LeaveRequest
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


def format_request_status(
    request: LeaveRequest,
    selected_leave_period: LeavePeriod | None = None,
) -> str:
    raw_status = _status_value(request.status)
    lines = [
        f"Заявка #{request.id}",
        f"Raw status: {raw_status}",
        f"Статус: {request_status_label(request.status)}",
    ]
    if selected_leave_period is not None:
        lines.append(
            "Даты: "
            f"{selected_leave_period.starts_on} — {selected_leave_period.ends_on} "
            f"({selected_leave_period.days_count} дн.)"
        )
    lines.append(f"Далее: {_next_action_hint(request.status)}")
    return "\n".join(lines)


def format_request_list_status(requests: tuple[LeaveRequest, ...]) -> str:
    lines = ["Ваши последние заявки:"]
    for request in requests:
        lines.append(
            f"#{request.id}: {request_status_label(request.status)}; "
            f"желательно с {request.desired_start_date}, {request.desired_days_count} дн.; "
            f"далее: {_next_action_hint(request.status)}"
        )
    return "\n".join(lines)


def _status_value(status: object) -> str:
    return str(getattr(status, "value", status))


def request_status_label(status: object) -> str:
    value = _status_value(status)
    labels = {
        RequestStatus.DRAFT.value: "черновик",
        RequestStatus.OPTIONS_GENERATED.value: "варианты подобраны",
        RequestStatus.SELECTED_BY_USER.value: "вариант выбран",
        RequestStatus.WAITING_AFFECTED_PEOPLE.value: "ожидает согласия затронутых людей",
        RequestStatus.WAITING_ADMIN_REVIEW.value: "ожидает проверки администратора",
        RequestStatus.WAITING_COMMANDER_APPROVAL.value: "ожидает согласования командира",
        RequestStatus.APPROVED_BY_COMMANDER.value: "согласована командиром",
        RequestStatus.READY_TO_APPLY.value: "готова к применению",
        RequestStatus.APPLIED.value: "применена",
        RequestStatus.REJECTED.value: "отклонена",
        RequestStatus.EXPIRED.value: "истекла",
        RequestStatus.CANCELLED.value: "отменена",
        RequestStatus.MANUAL_ADMIN_REVIEW_REQUIRED.value: "нужна ручная проверка администратора",
    }
    return labels.get(value, "неизвестный статус")


def _next_action_hint(status: object) -> str:
    value = _status_value(status)
    hints = {
        RequestStatus.OPTIONS_GENERATED.value: "выберите вариант отпуска",
        RequestStatus.SELECTED_BY_USER.value: "натисніть «Подати на погодження»",
        RequestStatus.WAITING_COMMANDER_APPROVAL.value: "ожидайте /commander_approve <request_id>",
        RequestStatus.APPROVED_BY_COMMANDER.value: "администратор выполняет /mark_ready <request_id>",
        RequestStatus.READY_TO_APPLY.value: "администратор выполняет /mark_applied <request_id>",
        RequestStatus.APPLIED.value: "ничего не требуется, заявка применена",
        RequestStatus.CANCELLED.value: "ничего не требуется, заявка отменена",
        RequestStatus.REJECTED.value: "создайте новую заявку при необходимости",
        RequestStatus.EXPIRED.value: "создайте новую заявку",
    }
    return hints.get(value, "проверьте заявку или обратитесь к администратору")

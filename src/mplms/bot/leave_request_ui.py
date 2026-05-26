"""Presentation helpers for Telegram leave request flow (Ukrainian UX)."""

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

# Snippets that must not appear in texts actually sent to Telegram users.
USER_FACING_FORBIDDEN_SNIPPETS: tuple[str, ...] = tuple(
    status.value for status in RequestStatus
) + (
    "Raw status",
    "scheduler",
    "demo-flow",
    "demo_flow",
    "Demo-flow",
    "CLI",
    "Personnel id",
    "Commander id",
    "traceback",
    "ValueError",
    "request_id",
    "<request_id>",
    "/commander_approve",
    "/mark_ready",
    "/mark_applied",
    "/demo_flow",
)


def default_desired_start(*, today: date | None = None) -> date:
    base = today or date.today()
    return base + timedelta(days=REQUEST_START_OFFSET_DAYS)


def format_date_ua(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def format_option_line(index: int, option: ScheduleOption) -> str:
    return (
        f"{index + 1}. {format_date_ua(option.start_date)} — "
        f"{format_date_ua(option.end_date)} ({option.duration_days} дн.)"
    )


def format_no_options_message(request_id: str) -> str:
    return (
        f"Заявку №{request_id} створено, але зараз немає доступних варіантів дат. "
        "Зверніться до адміністратора або спробуйте пізніше."
    )


def format_options_message(request_id: str, options: tuple[ScheduleOption, ...]) -> str:
    shown = options[:MAX_OPTIONS_TO_SHOW]
    lines = [
        f"Заявка №{request_id} створена.",
        f"Бажана дата початку: {format_date_ua(default_desired_start())}",
        f"Тривалість: {REQUEST_DURATION_DAYS} дн.",
        "",
        "Варіанти відпустки:",
    ]
    lines.extend(format_option_line(index, option) for index, option in enumerate(shown))
    lines.append("\nОберіть варіант кнопкою нижче.")
    return "\n".join(lines)


def format_request_status(
    request: LeaveRequest,
    selected_leave_period: LeavePeriod | None = None,
) -> str:
    lines = [
        f"Заявка №{request.id}",
        f"Статус: {request_status_label(request.status)}",
    ]
    if selected_leave_period is not None:
        lines.append(
            "Дати: "
            f"{format_date_ua(selected_leave_period.starts_on)} — "
            f"{format_date_ua(selected_leave_period.ends_on)}"
        )
    lines.append(f"Наступний крок: {_next_action_hint(request.status)}")
    return "\n".join(lines)


def format_request_summary_line(
    request: LeaveRequest,
    selected_leave_period: LeavePeriod | None = None,
) -> str:
    parts = [
        f"№{request.id}",
        request_status_label(request.status),
    ]
    if selected_leave_period is not None:
        parts.append(
            f"{format_date_ua(selected_leave_period.starts_on)} — "
            f"{format_date_ua(selected_leave_period.ends_on)}"
        )
    else:
        parts.append(
            f"бажано з {format_date_ua(request.desired_start_date)}, "
            f"{request.desired_days_count} дн."
        )
    return " · ".join(parts)


def format_request_list_status(requests: tuple[LeaveRequest, ...]) -> str:
    if not requests:
        return "У вас поки немає заявок."
    lines = ["Ваші останні заявки:"]
    for request in requests:
        lines.append(format_request_summary_line(request))
        lines.append(f"  Наступний крок: {_next_action_hint(request.status)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_pending_commander_list(
    items: tuple[tuple[LeaveRequest, LeavePeriod | None], ...],
) -> str:
    if not items:
        return "Немає заявок, що очікують погодження командира."
    lines = ["Заявки на погодження:"]
    for request, leave_period in items:
        lines.append("")
        lines.append(format_request_status(request, leave_period))
    return "\n".join(lines)


def format_admin_actions_list(
    approved: tuple[tuple[LeaveRequest, LeavePeriod | None], ...],
    ready: tuple[tuple[LeaveRequest, LeavePeriod | None], ...],
) -> str:
    if not approved and not ready:
        return "Немає заявок для адмін-дій."
    lines = ["Адмін-дії — заявки після погодження командиром:"]
    if approved:
        lines.append("")
        lines.append("Потрібно позначити готовими:")
        for request, leave_period in approved:
            lines.append("")
            lines.append(format_request_status(request, leave_period))
    if ready:
        lines.append("")
        lines.append("Готові до внесення в графік:")
        for request, leave_period in ready:
            lines.append("")
            lines.append(format_request_status(request, leave_period))
    return "\n".join(lines)


def _status_value(status: object) -> str:
    return str(getattr(status, "value", status))


def request_status_label(status: object) -> str:
    value = _status_value(status)
    labels = {
        RequestStatus.DRAFT.value: "чернетка",
        RequestStatus.OPTIONS_GENERATED.value: "варіанти підібрано",
        RequestStatus.SELECTED_BY_USER.value: "варіант відпустки обрано",
        RequestStatus.WAITING_AFFECTED_PEOPLE.value: "очікує погодження зачеплених осіб",
        RequestStatus.WAITING_ADMIN_REVIEW.value: "очікує перевірки адміністратора",
        RequestStatus.WAITING_COMMANDER_APPROVAL.value: "очікує погодження командира",
        RequestStatus.APPROVED_BY_COMMANDER.value: "погоджено командиром",
        RequestStatus.READY_TO_APPLY.value: "готово до внесення в графік",
        RequestStatus.APPLIED.value: "внесено в графік відпусток",
        RequestStatus.REJECTED.value: "відхилено",
        RequestStatus.EXPIRED.value: "термін минув",
        RequestStatus.CANCELLED.value: "скасовано",
        RequestStatus.MANUAL_ADMIN_REVIEW_REQUIRED.value: "потрібна ручна перевірка адміністратора",
    }
    return labels.get(value, "невідомий статус")


def _next_action_hint(status: object) -> str:
    value = _status_value(status)
    hints = {
        RequestStatus.OPTIONS_GENERATED.value: "оберіть варіант відпустки кнопкою нижче",
        RequestStatus.SELECTED_BY_USER.value: "натисніть «Подати на погодження»",
        RequestStatus.WAITING_COMMANDER_APPROVAL.value: "очікуйте рішення командира",
        RequestStatus.APPROVED_BY_COMMANDER.value: "очікуйте дії адміністратора",
        RequestStatus.READY_TO_APPLY.value: "очікуйте внесення в графік адміністратором",
        RequestStatus.APPLIED.value: "нічого не потрібно, заявка внесена в графік",
        RequestStatus.CANCELLED.value: "нічого не потрібно, заявку скасовано",
        RequestStatus.REJECTED.value: "за потреби створіть нову заявку",
        RequestStatus.EXPIRED.value: "створіть нову заявку",
    }
    return hints.get(value, "перевірте заявку або зверніться до адміністратора")


def contains_forbidden_user_text(text: str) -> list[str]:
    """Return forbidden snippets found in user-facing Telegram message text."""
    lowered = text.lower()
    found: list[str] = []
    for snippet in USER_FACING_FORBIDDEN_SNIPPETS:
        if snippet.lower() in lowered:
            found.append(snippet)
    return found

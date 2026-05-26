from __future__ import annotations

from unittest.mock import patch

import pytest

from mplms.bot import handlers
from mplms.bot.handlers import _HELP_TEXT
from mplms.bot.handlers import format_demo_flow_result
from mplms.bot.leave_request_ui import contains_forbidden_user_text
from mplms.bot.leave_request_ui import format_no_options_message
from mplms.bot.leave_request_ui import format_request_status
from mplms.bot.leave_request_ui import request_status_label
from mplms.cli import DemoFlowResult
from mplms.domain.enums import RequestStatus


class FakeMessage:
    def __init__(self, *, telegram_user_id: int = 1, text: str = "") -> None:
        self.from_user = type("FakeUser", (), {"id": telegram_user_id})()
        self.text = text
        self.answers: list[str] = []

    async def answer(self, text: str, reply_markup: object | None = None) -> None:
        self.answers.append(text)


def test_help_text_has_no_dev_markers() -> None:
    lowered = _HELP_TEXT.lower()
    assert "demo" not in lowered
    assert "cli" not in lowered
    assert "scheduler" not in lowered
    assert contains_forbidden_user_text(_HELP_TEXT) == []


def test_no_options_message_is_human_friendly() -> None:
    text = format_no_options_message("42")
    assert "№42" in text
    assert "варіантів дат" in text
    assert "scheduler" not in text.lower()
    assert contains_forbidden_user_text(text) == []


def test_demo_flow_result_has_no_internal_ids() -> None:
    result = DemoFlowResult(
        request_id="7",
        personnel_id="10",
        commander_id="20",
        final_status="applied",
        audit_events=(),
    )
    text = format_demo_flow_result(result)
    assert "№7" in text
    assert "внесено в графік" in text
    assert "personnel" not in text.lower()
    assert "commander id" not in text.lower()
    assert "demo" not in text.lower()
    assert contains_forbidden_user_text(text) == []


@pytest.mark.asyncio
async def test_demo_flow_disabled_in_non_local_env() -> None:
    message = FakeMessage(text="/demo_flow")
    with patch.object(handlers, "_demo_flow_enabled", return_value=False):
        await handlers.cmd_demo_flow(message)

    assert message.answers[-1] == "Не вдалося виконати дію. Спробуйте пізніше."
    assert contains_forbidden_user_text(message.answers[-1]) == []


@pytest.mark.asyncio
async def test_demo_flow_failure_hides_exception() -> None:
    message = FakeMessage(text="/demo_flow")
    with (
        patch.object(handlers, "_demo_flow_enabled", return_value=True),
        patch.object(handlers, "run_demo_flow", side_effect=RuntimeError("secret")),
    ):
        await handlers.cmd_demo_flow(message)

    assert message.answers[-1] == "Не вдалося виконати дію. Спробуйте пізніше."
    assert "secret" not in message.answers[-1]
    assert "runtimeerror" not in message.answers[-1].lower()


def test_format_request_status_uses_ukrainian_labels_only() -> None:
    from datetime import date

    from mplms.domain.enums import LeaveStatus
    from mplms.domain.enums import LeaveType
    from mplms.models.leave import LeavePeriod
    from mplms.models.workflow import LeaveRequest

    request = LeaveRequest(
        id=5,
        person_id=1,
        desired_start_date=date(2026, 6, 25),
        desired_days_count=15,
        status=RequestStatus.WAITING_COMMANDER_APPROVAL,
        policy_snapshot_id=1,
    )
    period = LeavePeriod(
        id=1,
        person_id=1,
        leave_type=LeaveType.ANNUAL_MAIN,
        year=2026,
        starts_on=date(2026, 6, 25),
        ends_on=date(2026, 7, 9),
        days_count=15,
        initial_starts_on=date(2026, 6, 25),
        initial_ends_on=date(2026, 7, 9),
        status=LeaveStatus.PLANNED,
        is_frozen=False,
        policy_snapshot_id=1,
    )
    text = format_request_status(request, period)
    assert request_status_label(RequestStatus.WAITING_COMMANDER_APPROVAL) in text
    assert contains_forbidden_user_text(text) == []

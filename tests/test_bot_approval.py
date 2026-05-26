from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from mplms.bot import handlers
from mplms.bot.keyboards import approval_keyboard
from mplms.bot.session import LeaveRequestSession
from mplms.bot.session import SUBMIT_APPROVAL_CALLBACK
from mplms.bot.session import leave_request_sessions
from mplms.domain.enums import LeaveStatus
from mplms.domain.enums import LeaveType
from mplms.domain.enums import RequestStatus
from mplms.domain.enums import UserRole
from mplms.models.leave import LeavePeriod
from mplms.models.personnel import Personnel
from mplms.models.personnel import Unit
from mplms.models.policy import PolicySnapshot
from mplms.models.workflow import LeaveRequest
from mplms.services.scheduler import ScheduleOption


class FakeMessage:
    def __init__(self, *, telegram_user_id: int = 1001, text: str = "") -> None:
        self.from_user = type(
            "FakeUser",
            (),
            {"id": telegram_user_id, "full_name": "Test Telegram User"},
        )()
        self.text = text
        self.answers: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup: object | None = None) -> None:
        self.answers.append((text, reply_markup))


class FakeCallback:
    def __init__(
        self,
        *,
        telegram_user_id: int = 1001,
        data: str = SUBMIT_APPROVAL_CALLBACK,
    ) -> None:
        self.from_user = type("FakeUser", (), {"id": telegram_user_id})()
        self.message = FakeMessage(telegram_user_id=telegram_user_id)
        self.data = data
        self.answers: list[tuple[str, bool | None]] = []

    async def answer(self, text: str, show_alert: bool | None = None) -> None:
        self.answers.append((text, show_alert))


def test_approval_keyboard_is_created() -> None:
    keyboard = approval_keyboard()

    button = keyboard.inline_keyboard[0][0]
    assert button.text == "Подати на погодження"
    assert button.callback_data == SUBMIT_APPROVAL_CALLBACK


@pytest.mark.asyncio
async def test_submit_approval_without_session_is_safe() -> None:
    leave_request_sessions.clear(91001)
    callback = FakeCallback(telegram_user_id=91001)

    await handlers.on_submit_approval(callback)

    assert callback.answers[-1] == ("Активная заявка не найдена.", True)
    assert "Нет активной заявки" in callback.message.answers[-1][0]


@pytest.mark.asyncio
async def test_my_request_shows_status(db_engine, monkeypatch) -> None:
    session_factory = async_sessionmaker(
        db_engine,
        expire_on_commit=False,
        autobegin=False,
    )
    request_id = await _seed_selected_request(session_factory)
    monkeypatch.setattr(handlers, "get_session_factory", _factory_provider(session_factory))
    leave_request_sessions.save(92001, LeaveRequestSession(request_id=request_id, options=()))
    message = FakeMessage(telegram_user_id=92001, text="/my_request")

    await handlers.cmd_my_request(message)

    text = message.answers[-1][0]
    assert f"Заявка #{request_id}" in text
    assert "Статус: selected_by_user" in text
    assert "Даты: 2026-08-01" in text


@pytest.mark.asyncio
async def test_submit_approval_callback_moves_request_to_waiting(
    db_engine,
    monkeypatch,
) -> None:
    session_factory = async_sessionmaker(
        db_engine,
        expire_on_commit=False,
        autobegin=False,
    )
    request_id = await _seed_selected_request(session_factory)
    monkeypatch.setattr(handlers, "get_session_factory", _factory_provider(session_factory))
    leave_request_sessions.save(
        93001,
        LeaveRequestSession(request_id=request_id, options=(_option(),)),
    )
    callback = FakeCallback(telegram_user_id=93001)

    await handlers.on_submit_approval(callback)

    async with session_factory() as session, session.begin():
        request = await session.get(LeaveRequest, int(request_id))

    assert request is not None
    assert request.status == RequestStatus.WAITING_COMMANDER_APPROVAL
    assert "waiting_commander_approval" in callback.message.answers[-1][0]


def _factory_provider(session_factory):
    async def get_session_factory():
        return session_factory

    return get_session_factory


def _option() -> ScheduleOption:
    return ScheduleOption(
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 15),
        duration_days=15,
        conflict_score=0,
        overlap_count=0,
        max_absent_on_any_day=1,
        reasons=["ok"],
    )


async def _seed_selected_request(session_factory) -> str:
    async with session_factory() as session, session.begin():
        unit = Unit(name="Bot Approval Test Unit", normal_overlap_limit=2)
        session.add(unit)
        await session.flush()

        policy = PolicySnapshot(
            legal_rules_version="bot-approval-test-legal",
            internal_policy_version="bot-approval-test-internal",
            legal_rules={},
            internal_rules={},
            effective_from=date(2026, 1, 1),
            is_active=True,
        )
        session.add(policy)
        await session.flush()

        applicant = Personnel(
            full_name="Bot Approval Applicant",
            role=UserRole.PERSONNEL,
            unit_id=unit.id,
        )
        session.add(applicant)
        await session.flush()

        leave_period = LeavePeriod(
            person_id=applicant.id,
            leave_type=LeaveType.ANNUAL_MAIN,
            year=2026,
            starts_on=date(2026, 8, 1),
            ends_on=date(2026, 8, 15),
            days_count=15,
            initial_starts_on=date(2026, 8, 1),
            initial_ends_on=date(2026, 8, 15),
            status=LeaveStatus.PLANNED,
            is_frozen=False,
            policy_snapshot_id=policy.id,
        )
        session.add(leave_period)
        await session.flush()

        request = LeaveRequest(
            person_id=applicant.id,
            desired_start_date=date(2026, 8, 1),
            desired_days_count=15,
            status=RequestStatus.SELECTED_BY_USER,
            policy_snapshot_id=policy.id,
            selected_leave_period_id=leave_period.id,
        )
        session.add(request)
        await session.flush()

        leave_period.source_request_id = request.id
        await session.flush()
        return str(request.id)

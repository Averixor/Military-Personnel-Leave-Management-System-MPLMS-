from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from mplms.bot import handlers
from mplms.bot.session import LEAVE_PICK_PREFIX
from mplms.bot.session import SUBMIT_APPROVAL_CALLBACK
from mplms.bot.session import leave_request_sessions
from mplms.domain.enums import RequestStatus
from mplms.domain.enums import UserRole
from mplms.models.audit import AuditLog
from mplms.models.personnel import Personnel
from mplms.models.personnel import Unit
from mplms.models.workflow import LeaveRequest


USER_TELEGRAM_ID = 70101
COMMANDER_TELEGRAM_ID = 70102
ADMIN_TELEGRAM_ID = 70103


class FakeMessage:
    def __init__(self, *, telegram_user_id: int, text: str) -> None:
        self.from_user = type(
            "FakeUser",
            (),
            {"id": telegram_user_id, "full_name": f"Telegram {telegram_user_id}"},
        )()
        self.text = text
        self.answers: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup: object | None = None) -> None:
        self.answers.append((text, reply_markup))


class FakeCallback:
    def __init__(self, *, telegram_user_id: int, data: str) -> None:
        self.from_user = type("FakeUser", (), {"id": telegram_user_id})()
        self.message = FakeMessage(telegram_user_id=telegram_user_id, text="")
        self.data = data
        self.answers: list[tuple[str, bool | None]] = []

    async def answer(self, text: str, show_alert: bool | None = None) -> None:
        self.answers.append((text, show_alert))


@pytest.mark.asyncio
async def test_full_bot_flow_reaches_applied_and_writes_audit(
    db_engine,
    monkeypatch,
) -> None:
    session_factory = _session_factory(db_engine)
    monkeypatch.setattr(handlers, "get_session_factory", _factory_provider(session_factory))
    leave_request_sessions.clear(USER_TELEGRAM_ID)
    await _seed_role_user(session_factory, telegram_id=COMMANDER_TELEGRAM_ID, role=UserRole.COMMANDER)
    await _seed_role_user(session_factory, telegram_id=ADMIN_TELEGRAM_ID, role=UserRole.ADMIN)

    await handlers.cmd_request_leave(
        FakeMessage(telegram_user_id=USER_TELEGRAM_ID, text="/request_leave")
    )
    bot_session = leave_request_sessions.get(USER_TELEGRAM_ID)
    assert bot_session is not None
    request_id = bot_session.request_id

    pick = FakeCallback(telegram_user_id=USER_TELEGRAM_ID, data=f"{LEAVE_PICK_PREFIX}0")
    await handlers.on_leave_option_picked(pick)
    assert "Raw status: selected_by_user" in pick.message.answers[-1][0]

    submit = FakeCallback(telegram_user_id=USER_TELEGRAM_ID, data=SUBMIT_APPROVAL_CALLBACK)
    await handlers.on_submit_approval(submit)
    assert "Raw status: waiting_commander_approval" in submit.message.answers[-1][0]

    commander_message = FakeMessage(
        telegram_user_id=COMMANDER_TELEGRAM_ID,
        text=f"/commander_approve {request_id}",
    )
    await handlers.cmd_commander_approve(commander_message)
    assert "Raw status: approved_by_commander" in commander_message.answers[-1][0]

    ready_message = FakeMessage(
        telegram_user_id=ADMIN_TELEGRAM_ID,
        text=f"/mark_ready {request_id}",
    )
    await handlers.cmd_mark_ready(ready_message)
    assert "Raw status: ready_to_apply" in ready_message.answers[-1][0]

    applied_message = FakeMessage(
        telegram_user_id=ADMIN_TELEGRAM_ID,
        text=f"/mark_applied {request_id}",
    )
    await handlers.cmd_mark_applied(applied_message)
    assert "Raw status: applied" in applied_message.answers[-1][0]

    my_request = FakeMessage(telegram_user_id=USER_TELEGRAM_ID, text="/my_request")
    await handlers.cmd_my_request(my_request)
    assert "Raw status: applied" in my_request.answers[-1][0]
    assert "Даты:" in my_request.answers[-1][0]

    async with session_factory() as session, session.begin():
        request = await session.get(LeaveRequest, int(request_id))
        audit_actions = (
            await session.execute(
                select(AuditLog.action).where(AuditLog.entity_id == int(request_id))
            )
        ).scalars().all()

    assert request is not None
    assert request.status == RequestStatus.APPLIED
    assert {
        "leave_request_created",
        "leave_option_selected",
        "submitted_for_approval",
        "commander_approved",
        "ready_to_apply",
        "applied",
    }.issubset(set(audit_actions))


@pytest.mark.asyncio
async def test_personnel_cannot_commander_approve_in_e2e_style(
    db_engine,
    monkeypatch,
) -> None:
    session_factory = _session_factory(db_engine)
    monkeypatch.setattr(handlers, "get_session_factory", _factory_provider(session_factory))
    await _seed_role_user(session_factory, telegram_id=USER_TELEGRAM_ID, role=UserRole.PERSONNEL)
    request_id = await _seed_request_for_status(
        session_factory,
        status=RequestStatus.WAITING_COMMANDER_APPROVAL,
    )
    message = FakeMessage(
        telegram_user_id=USER_TELEGRAM_ID,
        text=f"/commander_approve {request_id}",
    )

    await handlers.cmd_commander_approve(message)

    assert "Недостаточно прав" in message.answers[-1][0]
    async with session_factory() as session, session.begin():
        request = await session.get(LeaveRequest, int(request_id))
    assert request is not None
    assert request.status == RequestStatus.WAITING_COMMANDER_APPROVAL


@pytest.mark.asyncio
async def test_commander_cannot_mark_applied_in_e2e_style(
    db_engine,
    monkeypatch,
) -> None:
    session_factory = _session_factory(db_engine)
    monkeypatch.setattr(handlers, "get_session_factory", _factory_provider(session_factory))
    await _seed_role_user(session_factory, telegram_id=COMMANDER_TELEGRAM_ID, role=UserRole.COMMANDER)
    request_id = await _seed_request_for_status(
        session_factory,
        status=RequestStatus.READY_TO_APPLY,
    )
    message = FakeMessage(
        telegram_user_id=COMMANDER_TELEGRAM_ID,
        text=f"/mark_applied {request_id}",
    )

    await handlers.cmd_mark_applied(message)

    assert "Недостаточно прав" in message.answers[-1][0]
    async with session_factory() as session, session.begin():
        request = await session.get(LeaveRequest, int(request_id))
    assert request is not None
    assert request.status == RequestStatus.READY_TO_APPLY


@pytest.mark.asyncio
async def test_repeated_submit_is_handled_safely(db_engine, monkeypatch) -> None:
    session_factory = _session_factory(db_engine)
    monkeypatch.setattr(handlers, "get_session_factory", _factory_provider(session_factory))
    leave_request_sessions.clear(USER_TELEGRAM_ID)

    await handlers.cmd_request_leave(
        FakeMessage(telegram_user_id=USER_TELEGRAM_ID, text="/request_leave")
    )
    request_id = leave_request_sessions.get(USER_TELEGRAM_ID).request_id  # type: ignore[union-attr]
    await handlers.on_leave_option_picked(
        FakeCallback(telegram_user_id=USER_TELEGRAM_ID, data=f"{LEAVE_PICK_PREFIX}0")
    )
    await handlers.on_submit_approval(
        FakeCallback(telegram_user_id=USER_TELEGRAM_ID, data=SUBMIT_APPROVAL_CALLBACK)
    )
    repeated = FakeCallback(telegram_user_id=USER_TELEGRAM_ID, data=SUBMIT_APPROVAL_CALLBACK)

    await handlers.on_submit_approval(repeated)

    assert "уже не ожидает отправки" in repeated.message.answers[-1][0]
    async with session_factory() as session, session.begin():
        request = await session.get(LeaveRequest, int(request_id))
    assert request is not None
    assert request.status == RequestStatus.WAITING_COMMANDER_APPROVAL


@pytest.mark.asyncio
async def test_cancel_applied_request_is_rejected_safely(db_engine, monkeypatch) -> None:
    session_factory = _session_factory(db_engine)
    monkeypatch.setattr(handlers, "get_session_factory", _factory_provider(session_factory))
    user_id = await _seed_role_user(
        session_factory,
        telegram_id=USER_TELEGRAM_ID,
        role=UserRole.PERSONNEL,
    )
    request_id = await _seed_request_for_status(
        session_factory,
        status=RequestStatus.APPLIED,
        person_id=int(user_id),
    )
    message = FakeMessage(
        telegram_user_id=USER_TELEGRAM_ID,
        text=f"/cancel_request {request_id}",
    )

    await handlers.cmd_cancel_request(message)

    assert "уже applied" in message.answers[-1][0]
    async with session_factory() as session, session.begin():
        request = await session.get(LeaveRequest, int(request_id))
    assert request is not None
    assert request.status == RequestStatus.APPLIED


def _session_factory(db_engine):
    return async_sessionmaker(
        db_engine,
        expire_on_commit=False,
        autobegin=False,
    )


def _factory_provider(session_factory):
    async def get_session_factory():
        return session_factory

    return get_session_factory


async def _seed_role_user(session_factory, *, telegram_id: int, role: UserRole) -> str:
    async with session_factory() as session, session.begin():
        unit = Unit(name=f"E2E Role Unit {telegram_id}", normal_overlap_limit=2)
        session.add(unit)
        await session.flush()
        person = Personnel(
            telegram_id=telegram_id,
            full_name=f"E2E User {telegram_id}",
            role=role,
            unit_id=unit.id,
        )
        session.add(person)
        await session.flush()
        return str(person.id)


async def _seed_request_for_status(
    session_factory,
    *,
    status: RequestStatus,
    person_id: int | None = None,
) -> str:
    from mplms.domain.enums import LeaveStatus
    from mplms.domain.enums import LeaveType
    from mplms.models.leave import LeavePeriod
    from mplms.models.policy import PolicySnapshot

    async with session_factory() as session, session.begin():
        unit = Unit(name=f"E2E Request Unit {status.value} {person_id}", normal_overlap_limit=2)
        session.add(unit)
        await session.flush()

        if person_id is None:
            person = Personnel(
                full_name=f"E2E Applicant {status.value}",
                role=UserRole.PERSONNEL,
                unit_id=unit.id,
            )
            session.add(person)
            await session.flush()
            person_id = person.id

        policy = PolicySnapshot(
            legal_rules_version=f"e2e-{status.value}-legal",
            internal_policy_version=f"e2e-{status.value}-internal",
            legal_rules={},
            internal_rules={},
            effective_from=date(2026, 1, 1),
            is_active=True,
        )
        session.add(policy)
        await session.flush()

        leave_period = LeavePeriod(
            person_id=person_id,
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
            person_id=person_id,
            desired_start_date=date(2026, 8, 1),
            desired_days_count=15,
            status=status,
            policy_snapshot_id=policy.id,
            selected_leave_period_id=leave_period.id,
        )
        session.add(request)
        await session.flush()
        leave_period.source_request_id = request.id
        await session.flush()
        return str(request.id)

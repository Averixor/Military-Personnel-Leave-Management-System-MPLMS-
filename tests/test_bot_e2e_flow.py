from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from mplms.bot import handlers
from mplms.bot.keyboards import BTN_ADMIN_ACTIONS
from mplms.bot.keyboards import BTN_COMMANDER_PENDING
from mplms.bot.leave_request_ui import contains_forbidden_user_text
from mplms.bot.leave_request_ui import request_status_label
from mplms.bot.session import ADMIN_MARK_APPLIED_PREFIX
from mplms.bot.session import ADMIN_MARK_READY_PREFIX
from mplms.bot.session import COMMANDER_APPROVE_PREFIX
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


def _assert_user_facing(text: str) -> None:
    assert contains_forbidden_user_text(text) == []


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
    pick_text = pick.message.answers[-1][0]
    _assert_user_facing(pick_text)
    assert request_status_label(RequestStatus.SELECTED_BY_USER) in pick_text

    submit = FakeCallback(telegram_user_id=USER_TELEGRAM_ID, data=SUBMIT_APPROVAL_CALLBACK)
    await handlers.on_submit_approval(submit)
    submit_text = submit.message.answers[-1][0]
    _assert_user_facing(submit_text)
    assert request_status_label(RequestStatus.WAITING_COMMANDER_APPROVAL) in submit_text

    commander_list = FakeMessage(
        telegram_user_id=COMMANDER_TELEGRAM_ID,
        text=BTN_COMMANDER_PENDING,
    )
    await handlers.cmd_commander_pending(commander_list)
    list_text = commander_list.answers[-1][0]
    _assert_user_facing(list_text)
    assert f"№{request_id}" in list_text
    keyboard = commander_list.answers[-1][1]
    assert keyboard is not None
    assert keyboard.inline_keyboard[0][0].callback_data == f"{COMMANDER_APPROVE_PREFIX}{request_id}"

    approve_cb = FakeCallback(
        telegram_user_id=COMMANDER_TELEGRAM_ID,
        data=f"{COMMANDER_APPROVE_PREFIX}{request_id}",
    )
    await handlers.on_commander_approve_callback(approve_cb)
    approve_text = approve_cb.message.answers[-1][0]
    _assert_user_facing(approve_text)
    assert request_status_label(RequestStatus.APPROVED_BY_COMMANDER) in approve_text

    admin_list = FakeMessage(telegram_user_id=ADMIN_TELEGRAM_ID, text=BTN_ADMIN_ACTIONS)
    await handlers.cmd_admin_actions(admin_list)
    admin_keyboard = admin_list.answers[-1][1]
    assert admin_keyboard is not None
    ready_button = admin_keyboard.inline_keyboard[0][0]
    assert ready_button.callback_data == f"{ADMIN_MARK_READY_PREFIX}{request_id}"

    ready_cb = FakeCallback(
        telegram_user_id=ADMIN_TELEGRAM_ID,
        data=f"{ADMIN_MARK_READY_PREFIX}{request_id}",
    )
    await handlers.on_admin_mark_ready_callback(ready_cb)
    ready_text = ready_cb.message.answers[-1][0]
    _assert_user_facing(ready_text)
    assert request_status_label(RequestStatus.READY_TO_APPLY) in ready_text

    admin_list_2 = FakeMessage(telegram_user_id=ADMIN_TELEGRAM_ID, text=BTN_ADMIN_ACTIONS)
    await handlers.cmd_admin_actions(admin_list_2)
    apply_keyboard = admin_list_2.answers[-1][1]
    assert apply_keyboard is not None
    apply_button = apply_keyboard.inline_keyboard[0][0]
    assert apply_button.callback_data == f"{ADMIN_MARK_APPLIED_PREFIX}{request_id}"

    applied_cb = FakeCallback(
        telegram_user_id=ADMIN_TELEGRAM_ID,
        data=f"{ADMIN_MARK_APPLIED_PREFIX}{request_id}",
    )
    await handlers.on_admin_mark_applied_callback(applied_cb)
    applied_text = applied_cb.message.answers[-1][0]
    _assert_user_facing(applied_text)
    assert request_status_label(RequestStatus.APPLIED) in applied_text

    my_request = FakeMessage(telegram_user_id=USER_TELEGRAM_ID, text="/my_request")
    await handlers.cmd_my_request(my_request)
    my_text = my_request.answers[-1][0]
    _assert_user_facing(my_text)
    assert request_status_label(RequestStatus.APPLIED) in my_text
    assert "Дати:" in my_text

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

    assert "Ця дія доступна лише командиру." in message.answers[-1][0]
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

    assert "Ця дія доступна лише адміністратору." in message.answers[-1][0]
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

    repeated_text = repeated.message.answers[-1][0].lower()
    assert "вже не очікує" in repeated_text or "уже на погодженні" in repeated_text
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

    assert "внесено в графік" in message.answers[-1][0]
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

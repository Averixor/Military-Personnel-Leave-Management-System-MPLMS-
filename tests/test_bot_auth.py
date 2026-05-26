from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from mplms.bot import handlers
from mplms.bot.auth import require_role
from mplms.bot.leave_request_ui import contains_forbidden_user_text
from mplms.bot.leave_request_ui import request_status_label
from mplms.domain.enums import LeaveStatus
from mplms.domain.enums import LeaveType
from mplms.domain.enums import RequestStatus
from mplms.domain.enums import UserRole
from mplms.models.leave import LeavePeriod
from mplms.models.personnel import Personnel
from mplms.models.personnel import Unit
from mplms.models.policy import PolicySnapshot
from mplms.models.workflow import LeaveRequest


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


@pytest.mark.asyncio
async def test_personnel_cannot_run_commander_or_admin_commands(
    db_engine,
    monkeypatch,
) -> None:
    session_factory = _session_factory(db_engine)
    await _seed_person(session_factory, telegram_id=101, role=UserRole.PERSONNEL)
    waiting_request_id = await _seed_request(
        session_factory,
        status=RequestStatus.WAITING_COMMANDER_APPROVAL,
    )
    approved_request_id = await _seed_request(
        session_factory,
        status=RequestStatus.APPROVED_BY_COMMANDER,
    )
    ready_request_id = await _seed_request(
        session_factory,
        status=RequestStatus.READY_TO_APPLY,
    )
    monkeypatch.setattr(handlers, "get_session_factory", _factory_provider(session_factory))

    commander_msg = FakeMessage(
        telegram_user_id=101,
        text=f"/commander_approve {waiting_request_id}",
    )
    ready_msg = FakeMessage(
        telegram_user_id=101,
        text=f"/mark_ready {approved_request_id}",
    )
    applied_msg = FakeMessage(
        telegram_user_id=101,
        text=f"/mark_applied {ready_request_id}",
    )
    await handlers.cmd_commander_approve(commander_msg)
    await handlers.cmd_mark_ready(ready_msg)
    await handlers.cmd_mark_applied(applied_msg)

    assert "Ця дія доступна лише командиру." in commander_msg.answers[-1][0]
    assert "Ця дія доступна лише адміністратору." in ready_msg.answers[-1][0]
    assert "Ця дія доступна лише адміністратору." in applied_msg.answers[-1][0]

    async with session_factory() as session, session.begin():
        waiting = await session.get(LeaveRequest, int(waiting_request_id))
        approved = await session.get(LeaveRequest, int(approved_request_id))
        ready = await session.get(LeaveRequest, int(ready_request_id))

    assert waiting is not None
    assert approved is not None
    assert ready is not None
    assert waiting.status == RequestStatus.WAITING_COMMANDER_APPROVAL
    assert approved.status == RequestStatus.APPROVED_BY_COMMANDER
    assert ready.status == RequestStatus.READY_TO_APPLY


@pytest.mark.asyncio
async def test_commander_can_approve_request(db_engine, monkeypatch) -> None:
    session_factory = _session_factory(db_engine)
    await _seed_person(session_factory, telegram_id=202, role=UserRole.COMMANDER)
    request_id = await _seed_request(
        session_factory,
        status=RequestStatus.WAITING_COMMANDER_APPROVAL,
    )
    monkeypatch.setattr(handlers, "get_session_factory", _factory_provider(session_factory))
    message = FakeMessage(telegram_user_id=202, text=f"/commander_approve {request_id}")

    await handlers.cmd_commander_approve(message)

    async with session_factory() as session, session.begin():
        request = await session.get(LeaveRequest, int(request_id))

    assert request is not None
    assert request.status == RequestStatus.APPROVED_BY_COMMANDER
    text = message.answers[-1][0]
    assert request_status_label(RequestStatus.APPROVED_BY_COMMANDER) in text
    assert contains_forbidden_user_text(text) == []


@pytest.mark.asyncio
async def test_admin_can_mark_ready_and_applied(db_engine, monkeypatch) -> None:
    session_factory = _session_factory(db_engine)
    await _seed_person(session_factory, telegram_id=303, role=UserRole.ADMIN)
    request_id = await _seed_request(
        session_factory,
        status=RequestStatus.APPROVED_BY_COMMANDER,
    )
    monkeypatch.setattr(handlers, "get_session_factory", _factory_provider(session_factory))

    ready_msg = FakeMessage(telegram_user_id=303, text=f"/mark_ready {request_id}")
    await handlers.cmd_mark_ready(ready_msg)
    applied_msg = FakeMessage(telegram_user_id=303, text=f"/mark_applied {request_id}")
    await handlers.cmd_mark_applied(applied_msg)

    async with session_factory() as session, session.begin():
        request = await session.get(LeaveRequest, int(request_id))

    assert request is not None
    assert request.status == RequestStatus.APPLIED
    for text, _ in ready_msg.answers + applied_msg.answers:
        assert contains_forbidden_user_text(text) == []


@pytest.mark.asyncio
async def test_unknown_telegram_id_is_created_as_personnel(db_engine) -> None:
    session_factory = _session_factory(db_engine)

    async with session_factory() as session:
        person = await require_role(
            session,
            telegram_id=404,
            allowed_roles={UserRole.PERSONNEL.value},
        )

    assert person.telegram_id == 404
    assert person.role == UserRole.PERSONNEL


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


async def _seed_person(session_factory, *, telegram_id: int, role: UserRole) -> str:
    async with session_factory() as session, session.begin():
        unit = Unit(name=f"Auth Unit {telegram_id}", normal_overlap_limit=2)
        session.add(unit)
        await session.flush()
        person = Personnel(
            telegram_id=telegram_id,
            full_name=f"Auth User {telegram_id}",
            role=role,
            unit_id=unit.id,
        )
        session.add(person)
        await session.flush()
        return str(person.id)


async def _seed_request(session_factory, *, status: RequestStatus) -> str:
    async with session_factory() as session, session.begin():
        unit = Unit(name=f"Request Unit {status.value}", normal_overlap_limit=2)
        session.add(unit)
        await session.flush()

        policy = PolicySnapshot(
            legal_rules_version=f"auth-{status.value}-legal",
            internal_policy_version=f"auth-{status.value}-internal",
            legal_rules={},
            internal_rules={},
            effective_from=date(2026, 1, 1),
            is_active=True,
        )
        session.add(policy)
        await session.flush()

        applicant = Personnel(
            full_name=f"Applicant {status.value}",
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
            status=status,
            policy_snapshot_id=policy.id,
            selected_leave_period_id=leave_period.id,
        )
        session.add(request)
        await session.flush()

        leave_period.source_request_id = request.id
        await session.flush()
        return str(request.id)

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from mplms.bot import handlers
from mplms.bot.database import TelegramPersonnelNotFoundError
from mplms.bot.database import ensure_personnel_for_telegram
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
async def test_bot_finds_imported_personnel_by_telegram_id(db_engine) -> None:
    session_factory = _session_factory(db_engine)
    imported_id = await _seed_imported_personnel(
        session_factory,
        telegram_id=81001,
        role=UserRole.PERSONNEL,
    )

    person = await ensure_personnel_for_telegram(
        session_factory,
        telegram_user_id=81001,
        display_name="Different Telegram Name",
        auto_create=False,
    )

    assert person.id == int(imported_id)
    assert person.personnel_code == "IMP-81001"
    assert person.full_name == "Imported 81001"


@pytest.mark.asyncio
async def test_imported_commander_can_approve(db_engine, monkeypatch) -> None:
    session_factory = _session_factory(db_engine)
    await _seed_imported_personnel(
        session_factory,
        telegram_id=81002,
        role=UserRole.COMMANDER,
    )
    request_id = await _seed_request_for_status(
        session_factory,
        status=RequestStatus.WAITING_COMMANDER_APPROVAL,
    )
    monkeypatch.setattr(handlers, "get_session_factory", _factory_provider(session_factory))
    message = FakeMessage(telegram_user_id=81002, text=f"/commander_approve {request_id}")

    await handlers.cmd_commander_approve(message)

    assert "погоджено командиром" in message.answers[-1][0]
    assert "approved_by_commander" not in message.answers[-1][0]


@pytest.mark.asyncio
async def test_imported_admin_can_mark_applied(db_engine, monkeypatch) -> None:
    session_factory = _session_factory(db_engine)
    await _seed_imported_personnel(
        session_factory,
        telegram_id=81003,
        role=UserRole.ADMIN,
    )
    request_id = await _seed_request_for_status(
        session_factory,
        status=RequestStatus.READY_TO_APPLY,
    )
    monkeypatch.setattr(handlers, "get_session_factory", _factory_provider(session_factory))
    message = FakeMessage(telegram_user_id=81003, text=f"/mark_applied {request_id}")

    await handlers.cmd_mark_applied(message)

    assert "внесено в графік відпусток" in message.answers[-1][0]
    assert "applied" not in message.answers[-1][0].lower()


@pytest.mark.asyncio
async def test_inactive_personnel_cannot_create_request(db_engine, monkeypatch) -> None:
    session_factory = _session_factory(db_engine)
    await _seed_imported_personnel(
        session_factory,
        telegram_id=81004,
        role=UserRole.PERSONNEL,
        is_active=False,
    )
    monkeypatch.setattr(handlers, "get_session_factory", _factory_provider(session_factory))
    message = FakeMessage(telegram_user_id=81004, text="/request_leave")

    await handlers.cmd_request_leave(message)

    assert "неактивний" in message.answers[-1][0]
    async with session_factory() as session, session.begin():
        request_count = len((await session.execute(select(LeaveRequest))).scalars().all())
    assert request_count == 0


@pytest.mark.asyncio
async def test_unknown_telegram_id_creates_personnel_when_auto_create_enabled(db_engine) -> None:
    session_factory = _session_factory(db_engine)

    person = await ensure_personnel_for_telegram(
        session_factory,
        telegram_user_id=81005,
        display_name="Auto Created User",
        auto_create=True,
    )

    assert person.telegram_id == 81005
    assert person.role == UserRole.PERSONNEL
    assert person.is_active is True


@pytest.mark.asyncio
async def test_unknown_telegram_id_rejected_when_auto_create_disabled(db_engine) -> None:
    session_factory = _session_factory(db_engine)

    with pytest.raises(TelegramPersonnelNotFoundError):
        await ensure_personnel_for_telegram(
            session_factory,
            telegram_user_id=81006,
            display_name="Unknown User",
            auto_create=False,
        )


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


async def _seed_imported_personnel(
    session_factory,
    *,
    telegram_id: int,
    role: UserRole,
    is_active: bool = True,
) -> str:
    async with session_factory() as session, session.begin():
        unit = Unit(name=f"Imported Unit {telegram_id}", normal_overlap_limit=2)
        session.add(unit)
        await session.flush()
        person = Personnel(
            personnel_code=f"IMP-{telegram_id}",
            telegram_id=telegram_id,
            full_name=f"Imported {telegram_id}",
            rank="SGT",
            position="Imported Position",
            role=role,
            unit_id=unit.id,
            is_active=is_active,
        )
        session.add(person)
        await session.flush()
        return str(person.id)


async def _seed_request_for_status(session_factory, *, status: RequestStatus) -> str:
    async with session_factory() as session, session.begin():
        unit = Unit(name=f"Binding Request Unit {status.value}", normal_overlap_limit=2)
        session.add(unit)
        await session.flush()

        policy = PolicySnapshot(
            legal_rules_version=f"binding-{status.value}-legal",
            internal_policy_version=f"binding-{status.value}-internal",
            legal_rules={},
            internal_rules={},
            effective_from=date(2026, 1, 1),
            is_active=True,
        )
        session.add(policy)
        await session.flush()

        applicant = Personnel(
            full_name=f"Binding Applicant {status.value}",
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

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from mplms.domain.enums import UserRole
from mplms.models.personnel import Personnel
from mplms.services.personnel_import import import_personnel_csv


@pytest.mark.asyncio
async def test_import_creates_new_personnel(db_session, tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        [
            "P001,Alice Example,LT,Platoon Commander,commander,111,true",
            "P002,Bob Example,SGT,Rifleman,personnel,,yes",
        ],
    )

    result = await import_personnel_csv(db_session, csv_path)

    assert result.created_count == 2
    assert result.updated_count == 0
    assert result.skipped_count == 0
    async with db_session.begin():
        rows = (
            await db_session.execute(select(Personnel).order_by(Personnel.personnel_code))
        ).scalars().all()
    assert [row.personnel_code for row in rows] == ["P001", "P002"]
    assert rows[0].role == UserRole.COMMANDER
    assert rows[1].telegram_id is None


@pytest.mark.asyncio
async def test_repeated_import_updates_existing_personnel(db_session, tmp_path: Path) -> None:
    first = _write_csv(
        tmp_path,
        ["P010,Original Name,CPT,Old Position,personnel,222,true"],
        filename="first.csv",
    )
    second = _write_csv(
        tmp_path,
        ["P010,Updated Name,MAJ,New Position,admin,333,false"],
        filename="second.csv",
    )

    await import_personnel_csv(db_session, first)
    result = await import_personnel_csv(db_session, second)

    assert result.created_count == 0
    assert result.updated_count == 1
    async with db_session.begin():
        person = await db_session.scalar(
            select(Personnel).where(Personnel.personnel_code == "P010")
        )
    assert person is not None
    assert person.full_name == "Updated Name"
    assert person.rank == "MAJ"
    assert person.position == "New Position"
    assert person.role == UserRole.ADMIN
    assert person.telegram_id == 333
    assert person.is_active is False


@pytest.mark.asyncio
async def test_empty_telegram_id_is_allowed(db_session, tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path, ["P020,No Telegram,PVT,Clerk,personnel,,true"])

    await import_personnel_csv(db_session, csv_path)

    async with db_session.begin():
        person = await db_session.scalar(
            select(Personnel).where(Personnel.personnel_code == "P020")
        )
    assert person is not None
    assert person.telegram_id is None


@pytest.mark.asyncio
async def test_invalid_role_adds_error_without_aborting_import(db_session, tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        [
            "P030,Good User,SGT,Operator,personnel,444,true",
            "P031,Bad Role,SGT,Operator,deputy,555,true",
        ],
    )

    result = await import_personnel_csv(db_session, csv_path)

    assert result.created_count == 1
    assert result.skipped_count == 1
    assert "invalid role" in result.errors[0]
    async with db_session.begin():
        count = await db_session.scalar(select(Personnel).where(Personnel.personnel_code == "P030"))
        bad = await db_session.scalar(select(Personnel).where(Personnel.personnel_code == "P031"))
    assert count is not None
    assert bad is None


@pytest.mark.asyncio
async def test_is_active_values_are_parsed(db_session, tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        [
            "P040,True One,SGT,Operator,personnel,401,true",
            "P041,True Two,SGT,Operator,personnel,402,так",
            "P042,Default True,SGT,Operator,personnel,403,",
            "P043,False One,SGT,Operator,personnel,404,false",
            "P044,False Two,SGT,Operator,personnel,405,ні",
        ],
    )

    result = await import_personnel_csv(db_session, csv_path)

    assert result.errors == []
    async with db_session.begin():
        rows = (
            await db_session.execute(select(Personnel).order_by(Personnel.personnel_code))
        ).scalars().all()
    by_code = {row.personnel_code: row.is_active for row in rows}
    assert by_code == {
        "P040": True,
        "P041": True,
        "P042": True,
        "P043": False,
        "P044": False,
    }


def _write_csv(tmp_path: Path, rows: list[str], *, filename: str = "personnel.csv") -> Path:
    csv_path = tmp_path / filename
    csv_path.write_text(
        "personnel_code,full_name,rank,position,role,telegram_id,is_active\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )
    return csv_path

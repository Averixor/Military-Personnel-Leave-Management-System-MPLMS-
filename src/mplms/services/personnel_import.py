"""CSV import for personnel records."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from mplms.domain.enums import UserRole
from mplms.models.personnel import Personnel

CSV_COLUMNS = (
    "personnel_code",
    "full_name",
    "rank",
    "position",
    "role",
    "telegram_id",
    "is_active",
)
ALLOWED_ROLES = {
    UserRole.PERSONNEL.value,
    UserRole.COMMANDER.value,
    UserRole.ADMIN.value,
}
TRUE_VALUES = {"true", "1", "yes", "так", "да"}
FALSE_VALUES = {"false", "0", "no", "ні", "нет"}


@dataclass(frozen=True)
class ImportResult:
    created_count: int
    updated_count: int
    skipped_count: int
    errors: list[str]


@dataclass(frozen=True)
class _PersonnelRow:
    personnel_code: str
    full_name: str
    rank: str | None
    position: str | None
    role: UserRole
    telegram_id: int | None
    is_active: bool


async def import_personnel_csv(session: AsyncSession, csv_path: Path) -> ImportResult:
    created_count = 0
    updated_count = 0
    skipped_count = 0
    errors: list[str] = []

    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            missing_columns = [column for column in CSV_COLUMNS if column not in (reader.fieldnames or ())]
            if missing_columns:
                return ImportResult(
                    created_count=0,
                    updated_count=0,
                    skipped_count=0,
                    errors=[f"Missing CSV columns: {', '.join(missing_columns)}"],
                )
            rows = list(reader)
    except OSError as exc:
        return ImportResult(
            created_count=0,
            updated_count=0,
            skipped_count=0,
            errors=[f"Cannot read CSV file {csv_path}: {exc}"],
        )

    async with session.begin():
        for line_number, raw_row in enumerate(rows, start=2):
            try:
                parsed = _parse_row(raw_row, line_number)
            except ValueError as exc:
                skipped_count += 1
                errors.append(str(exc))
                continue

            try:
                async with session.begin_nested():
                    existing = await session.scalar(
                        select(Personnel).where(
                            Personnel.personnel_code == parsed.personnel_code
                        )
                    )
                    if existing is None:
                        person = Personnel(
                            personnel_code=parsed.personnel_code,
                            full_name=parsed.full_name,
                            rank=parsed.rank,
                            position=parsed.position,
                            role=parsed.role,
                            telegram_id=parsed.telegram_id,
                            is_active=parsed.is_active,
                        )
                        session.add(person)
                        await session.flush()
                        created_count += 1
                    else:
                        existing.full_name = parsed.full_name
                        existing.rank = parsed.rank
                        existing.position = parsed.position
                        existing.role = parsed.role
                        existing.telegram_id = parsed.telegram_id
                        existing.is_active = parsed.is_active
                        await session.flush()
                        updated_count += 1
            except SQLAlchemyError as exc:
                skipped_count += 1
                errors.append(f"Line {line_number}: database error: {exc}")

    return ImportResult(
        created_count=created_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
        errors=errors,
    )


def _parse_row(row: dict[str, str], line_number: int) -> _PersonnelRow:
    personnel_code = _required(row, "personnel_code", line_number)
    full_name = _required(row, "full_name", line_number)
    role = _parse_role(row.get("role", ""), line_number)
    return _PersonnelRow(
        personnel_code=personnel_code,
        full_name=full_name,
        rank=_optional(row.get("rank")),
        position=_optional(row.get("position")),
        role=role,
        telegram_id=_parse_telegram_id(row.get("telegram_id", ""), line_number),
        is_active=_parse_is_active(row.get("is_active", ""), line_number),
    )


def _required(row: dict[str, str], column: str, line_number: int) -> str:
    value = _optional(row.get(column))
    if value is None:
        raise ValueError(f"Line {line_number}: {column} is required")
    return value


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _parse_role(value: str, line_number: int) -> UserRole:
    normalized = value.strip().lower()
    if normalized not in ALLOWED_ROLES:
        allowed = ", ".join(sorted(ALLOWED_ROLES))
        raise ValueError(f"Line {line_number}: invalid role {value!r}; allowed: {allowed}")
    return UserRole(normalized)


def _parse_telegram_id(value: str, line_number: int) -> int | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError as exc:
        raise ValueError(f"Line {line_number}: invalid telegram_id {value!r}") from exc


def _parse_is_active(value: str, line_number: int) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return True
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"Line {line_number}: invalid is_active {value!r}")

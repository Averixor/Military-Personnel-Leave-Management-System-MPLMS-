"""Command-line tools for local MPLMS development."""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

import mplms.models  # noqa: F401 — register ORM models
from mplms.core.database import ensure_sqlite_data_dir
from mplms.core.database import engine_kwargs
from mplms.core.database import resolve_database_url
from mplms.domain.enums import LeaveType
from mplms.domain.enums import UserRole
from mplms.models import Base
from mplms.models.audit import AuditLog
from mplms.models.personnel import Personnel
from mplms.models.personnel import Unit
from mplms.models.policy import PolicySnapshot
from mplms.models.workflow import LeaveRequest
from mplms.services.approval_persistence import approve_by_commander
from mplms.services.approval_persistence import mark_applied
from mplms.services.approval_persistence import mark_ready_to_apply
from mplms.services.approval_persistence import submit_selected_request_for_approval
from mplms.services.audit import status_str
from mplms.services.leave_request_persistence import create_persisted_leave_request
from mplms.services.leave_request_persistence import select_persisted_leave_option
from mplms.services.personnel_import import ImportResult
from mplms.services.personnel_import import import_personnel_csv

DEMO_UNIT_NAME = "CLI Demo Unit"
DEMO_APPLICANT_NAME = "CLI Demo Applicant"
DEMO_COMMANDER_NAME = "CLI Demo Commander"


@dataclass(frozen=True)
class AuditEventSummary:
    action: str
    before_state: dict | None
    after_state: dict | None


@dataclass(frozen=True)
class DemoFlowResult:
    request_id: str
    personnel_id: str
    commander_id: str
    final_status: str
    audit_events: tuple[AuditEventSummary, ...]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mplms.cli")
    subparsers = parser.add_subparsers(dest="command")

    demo_parser = subparsers.add_parser(
        "demo-flow",
        help="Run the full leave-request DB flow on SQLite (no Docker/Telegram).",
    )
    demo_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL (default: dev SQLite file).",
    )
    import_parser = subparsers.add_parser(
        "import-personnel",
        help="Import personnel from CSV into the configured database.",
    )
    import_parser.add_argument("csv_path", type=Path)
    import_parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL (default: dev SQLite file).",
    )

    args = parser.parse_args(argv)
    if args.command == "demo-flow":
        asyncio.run(run_demo_flow(database_url=args.database_url, verbose=True))
        return 0
    if args.command == "import-personnel":
        result = asyncio.run(
            run_import_personnel(
                csv_path=args.csv_path,
                database_url=args.database_url,
                verbose=True,
            )
        )
        return 1 if result.errors and result.created_count == 0 and result.updated_count == 0 else 0

    parser.print_help()
    return 1


async def run_import_personnel(
    *,
    csv_path: Path,
    database_url: str | None = None,
    verbose: bool = True,
) -> ImportResult:
    url = resolve_database_url(database_url)
    ensure_sqlite_data_dir(url)

    engine = create_async_engine(url, **engine_kwargs(url))
    session_factory = async_sessionmaker(engine, expire_on_commit=False, autobegin=False)
    try:
        await _init_schema(engine)
        await _ensure_personnel_import_schema(engine)
        async with session_factory() as session:
            result = await import_personnel_csv(session, csv_path)
        _print_import_result(result, csv_path=csv_path, url=url, verbose=verbose)
        return result
    finally:
        await engine.dispose()


async def run_demo_flow(
    *,
    database_url: str | None = None,
    verbose: bool = True,
) -> DemoFlowResult:
    url = resolve_database_url(database_url)
    ensure_sqlite_data_dir(url)

    engine = create_async_engine(url, **engine_kwargs(url))
    session_factory = async_sessionmaker(engine, expire_on_commit=False, autobegin=False)

    try:
        await _init_schema(engine)
        personnel_id, commander_id = await _ensure_demo_personnel(session_factory)

        async with session_factory() as session:
            created = await create_persisted_leave_request(
                session,
                personnel_id=personnel_id,
                desired_start=date(2026, 6, 15),
                duration_days=5,
                leave_type=LeaveType.ANNUAL_MAIN.value,
                max_shift_days=0,
            )
        _print_options(created.request_id, created.options, verbose=verbose)

        option = created.options[0]
        async with session_factory() as session:
            await select_persisted_leave_option(
                session,
                request_id=created.request_id,
                option=option,
            )
        async with session_factory() as session:
            await submit_selected_request_for_approval(session, request_id=created.request_id)
        async with session_factory() as session:
            await approve_by_commander(
                session,
                request_id=created.request_id,
                commander_id=commander_id,
            )
        async with session_factory() as session:
            await mark_ready_to_apply(session, request_id=created.request_id)
        async with session_factory() as session:
            await mark_applied(session, request_id=created.request_id)

        final_status, audit_events = await _load_request_summary(
            session_factory,
            created.request_id,
        )
        result = DemoFlowResult(
            request_id=created.request_id,
            personnel_id=personnel_id,
            commander_id=commander_id,
            final_status=final_status,
            audit_events=audit_events,
        )
        _print_summary(result, url=url, verbose=verbose)
        return result
    finally:
        await engine.dispose()


async def _init_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def _ensure_personnel_import_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        columns = await connection.run_sync(
            lambda sync_conn: {
                column["name"] for column in sa.inspect(sync_conn).get_columns("personnel")
            }
        )
        if "personnel_code" not in columns:
            await connection.execute(
                sa.text("ALTER TABLE personnel ADD COLUMN personnel_code VARCHAR(100)")
            )
        if "position" not in columns:
            await connection.execute(
                sa.text("ALTER TABLE personnel ADD COLUMN position VARCHAR(255)")
            )
        await connection.execute(
            sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_personnel_personnel_code "
                "ON personnel (personnel_code)"
            )
        )


async def _ensure_demo_personnel(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[str, str]:
    async with session_factory() as session, session.begin():
        unit = await session.scalar(select(Unit).where(Unit.name == DEMO_UNIT_NAME))
        if unit is None:
            unit = Unit(name=DEMO_UNIT_NAME, normal_overlap_limit=2)
            session.add(unit)
            await session.flush()

        policy = await session.scalar(
            select(PolicySnapshot).where(PolicySnapshot.is_active.is_(True)).limit(1)
        )
        if policy is None:
            policy = PolicySnapshot(
                legal_rules_version="cli-demo-legal",
                internal_policy_version="cli-demo-internal",
                legal_rules={},
                internal_rules={},
                effective_from=date(2026, 1, 1),
                is_active=True,
            )
            session.add(policy)
            await session.flush()

        applicant = await session.scalar(
            select(Personnel).where(Personnel.full_name == DEMO_APPLICANT_NAME)
        )
        if applicant is None:
            applicant = Personnel(
                full_name=DEMO_APPLICANT_NAME,
                role=UserRole.PERSONNEL,
                unit_id=unit.id,
            )
            session.add(applicant)
            await session.flush()

        commander = await session.scalar(
            select(Personnel).where(Personnel.full_name == DEMO_COMMANDER_NAME)
        )
        if commander is None:
            commander = Personnel(
                full_name=DEMO_COMMANDER_NAME,
                role=UserRole.COMMANDER,
                unit_id=unit.id,
            )
            session.add(commander)
            await session.flush()

        return str(applicant.id), str(commander.id)


async def _load_request_summary(
    session_factory: async_sessionmaker[AsyncSession],
    request_id: str,
) -> tuple[str, tuple[AuditEventSummary, ...]]:
    async with session_factory() as session, session.begin():
        request = await session.get(LeaveRequest, int(request_id))
        if request is None:
            raise ValueError(f"Leave request {request_id} was not found after demo flow")

        logs = (
            await session.execute(
                select(AuditLog)
                .where(
                    AuditLog.entity_type == "leave_request",
                    AuditLog.entity_id == int(request_id),
                )
                .order_by(AuditLog.id)
            )
        ).scalars().all()

        events = tuple(
            AuditEventSummary(
                action=log.action,
                before_state=log.before_state,
                after_state=log.after_state,
            )
            for log in logs
        )
        return status_str(request.status), events


def _print_options(request_id: str, options, *, verbose: bool) -> None:
    if not verbose:
        return
    print(f"\nLeave request #{request_id} - scheduler options:")
    for index, option in enumerate(options):
        print(
            f"  [{index}] {option.start_date} .. {option.end_date} "
            f"({option.duration_days}d, score={option.conflict_score}, "
            f"overlap={option.overlap_count})"
        )
    print("  -> selecting option [0]")


def _print_summary(result: DemoFlowResult, *, url: str, verbose: bool) -> None:
    if not verbose:
        return
    print(f"\nDatabase: {url}")
    print(f"Personnel id: {result.personnel_id}")
    print(f"Commander id: {result.commander_id}")
    print(f"Final request status: {result.final_status}")
    print(f"\nAudit trail for request #{result.request_id}:")
    for event in result.audit_events:
        print(
            f"  - {event.action}: "
            f"{event.before_state or {}} -> {event.after_state or {}}"
        )
    print("\nDemo flow completed successfully.")


def _print_import_result(
    result: ImportResult,
    *,
    csv_path: Path,
    url: str,
    verbose: bool,
) -> None:
    if not verbose:
        return
    print(f"\nDatabase: {url}")
    print(f"CSV: {csv_path}")
    print(f"Created: {result.created_count}")
    print(f"Updated: {result.updated_count}")
    print(f"Skipped: {result.skipped_count}")
    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"  - {error}")
    print("\nPersonnel import completed.")


if __name__ == "__main__":
    sys.exit(main())

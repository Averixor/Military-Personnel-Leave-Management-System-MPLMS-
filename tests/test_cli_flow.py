import asyncio
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

import mplms.models  # noqa: F401
from mplms.cli import AuditEventSummary
from mplms.cli import DemoFlowResult
from mplms.cli import main
from mplms.cli import run_demo_flow
from mplms.core.database import engine_kwargs
from mplms.domain.enums import RequestStatus
from mplms.models.workflow import LeaveRequest


def test_cli_module_imports() -> None:
    assert callable(main)
    assert asyncio.iscoroutinefunction(run_demo_flow)


@pytest.fixture
def cli_database_url(tmp_path: Path) -> str:
    db_file = tmp_path / "cli_demo.sqlite3"
    return f"sqlite+aiosqlite:///{db_file.as_posix()}"


def test_demo_flow_completes_with_applied_status_and_audits(cli_database_url: str) -> None:
    result = asyncio.run(
        run_demo_flow(database_url=cli_database_url, verbose=False),
    )

    assert isinstance(result, DemoFlowResult)
    assert result.final_status == RequestStatus.APPLIED.value
    assert result.request_id
    assert result.personnel_id
    assert result.commander_id

    actions = {event.action for event in result.audit_events}
    assert actions >= {
        "leave_request_created",
        "leave_option_selected",
        "submitted_for_approval",
        "commander_approved",
        "ready_to_apply",
        "applied",
    }
    assert all(isinstance(event, AuditEventSummary) for event in result.audit_events)

    asyncio.run(_assert_leave_request_applied(cli_database_url, result.request_id))


async def _assert_leave_request_applied(database_url: str, request_id: str) -> None:
    engine = create_async_engine(database_url, **engine_kwargs(database_url))
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            request = await session.get(LeaveRequest, int(request_id))
            assert request is not None
            assert request.status == RequestStatus.APPLIED
    finally:
        await engine.dispose()

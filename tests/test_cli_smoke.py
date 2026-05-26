import asyncio
from pathlib import Path

import pytest

from mplms.cli import AuditEventSummary
from mplms.cli import DemoFlowResult
from mplms.cli import main
from mplms.cli import run_demo_flow
from mplms.domain.enums import RequestStatus


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

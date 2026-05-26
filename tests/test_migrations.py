import mplms.models  # noqa: F401
from mplms.models import Base


def test_metadata_registers_core_tables() -> None:
    expected = {
        "personnel",
        "leave_periods",
        "leave_requests",
        "approval_steps",
        "conflict_groups",
        "policy_snapshots",
        "audit_logs",
        "snapshots",
        "documents",
        "override_audits",
    }
    assert expected.issubset(Base.metadata.tables.keys())

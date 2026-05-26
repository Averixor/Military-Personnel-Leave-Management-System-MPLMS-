"""Audit logging for persisted leave request workflow."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from mplms.domain.enums import RequestStatus
from mplms.models.audit import AuditLog


def status_str(status: RequestStatus | str) -> str:
    return status.value if isinstance(status, RequestStatus) else str(status)


async def create_audit_log(
    session: AsyncSession,
    entity_type: str,
    entity_id: str,
    operation: str,
    changed_by: str | None = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
    reason: str | None = None,
) -> AuditLog:
    log = AuditLog(
        actor_id=_parse_actor_id(changed_by),
        action=operation,
        entity_type=entity_type,
        entity_id=_parse_entity_id(entity_id),
        before_state=old_values,
        after_state=new_values,
        reason=reason,
    )
    session.add(log)
    await session.flush()
    return log


def _parse_actor_id(changed_by: str | None) -> int | None:
    if changed_by is None:
        return None
    try:
        return int(changed_by)
    except ValueError as exc:
        raise ValueError(f"Invalid changed_by: {changed_by!r}") from exc


def _parse_entity_id(entity_id: str) -> int:
    try:
        return int(entity_id)
    except ValueError as exc:
        raise ValueError(f"Invalid entity_id: {entity_id!r}") from exc

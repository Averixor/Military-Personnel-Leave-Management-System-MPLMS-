from sqlalchemy import ForeignKey
from sqlalchemy import JSON
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from mplms.models.base import Base
from mplms.models.base import CreatedAt


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("personnel.id"))
    actor_role: Mapped[str | None] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_id: Mapped[int | None] = mapped_column(index=True)
    before_state: Mapped[dict | None] = mapped_column(JSON)
    after_state: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[CreatedAt]


class OverrideAudit(Base):
    __tablename__ = "override_audits"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("personnel.id"), index=True)
    override_type: Mapped[str] = mapped_column(String(50), index=True)
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[int | None]
    reason: Mapped[str] = mapped_column(String(1000))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[CreatedAt]


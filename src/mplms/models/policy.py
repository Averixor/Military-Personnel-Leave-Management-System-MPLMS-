from datetime import date

from sqlalchemy import Boolean
from sqlalchemy import Date
from sqlalchemy import JSON
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from mplms.models.base import Base
from mplms.models.base import CreatedAt


class PolicySnapshot(Base):
    __tablename__ = "policy_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    legal_rules_version: Mapped[str] = mapped_column(String(50))
    internal_policy_version: Mapped[str] = mapped_column(String(50))
    legal_rules: Mapped[dict] = mapped_column(JSON, default=dict)
    internal_rules: Mapped[dict] = mapped_column(JSON, default=dict)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[int | None]
    created_at: Mapped[CreatedAt]


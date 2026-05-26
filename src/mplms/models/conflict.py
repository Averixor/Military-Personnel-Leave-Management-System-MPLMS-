from sqlalchemy import JSON
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from mplms.domain.enums import ConflictGroupType
from mplms.models.base import Base
from mplms.models.base import CreatedAt
from mplms.models.base import UpdatedAt


class ConflictGroup(Base):
    __tablename__ = "conflict_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    group_type: Mapped[ConflictGroupType] = mapped_column(String(50))
    member_personnel_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    rules: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


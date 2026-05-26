from sqlalchemy import JSON
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from mplms.models.base import Base
from mplms.models.base import CreatedAt


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_type: Mapped[str] = mapped_column(String(100), index=True)
    reason: Mapped[str] = mapped_column(String(500))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[int | None]
    created_at: Mapped[CreatedAt]


from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from mplms.domain.enums import CriticalityLevel
from mplms.domain.enums import UserRole
from mplms.models.base import Base
from mplms.models.base import CreatedAt
from mplms.models.base import UpdatedAt


class Personnel(Base):
    __tablename__ = "personnel"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    rank: Mapped[str | None] = mapped_column(String(100))
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"), index=True)
    role: Mapped[UserRole] = mapped_column(String(50), default=UserRole.PERSONNEL)
    commander_id: Mapped[int | None] = mapped_column(ForeignKey("personnel.id"))
    deputy_id: Mapped[int | None] = mapped_column(ForeignKey("personnel.id"))
    criticality_level: Mapped[CriticalityLevel] = mapped_column(String(10), default=CriticalityLevel.NORMAL)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    commander: Mapped["Personnel | None"] = relationship(
        remote_side=[id],
        foreign_keys=[commander_id],
    )
    deputy: Mapped["Personnel | None"] = relationship(
        remote_side=[id],
        foreign_keys=[deputy_id],
    )


class Unit(Base):
    __tablename__ = "units"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    normal_overlap_limit: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


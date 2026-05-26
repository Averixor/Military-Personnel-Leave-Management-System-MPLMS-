from datetime import date
from datetime import datetime

from sqlalchemy import Boolean
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from mplms.domain.enums import LeaveStatus
from mplms.domain.enums import LeaveType
from mplms.models.base import Base
from mplms.models.base import CreatedAt
from mplms.models.base import UpdatedAt


class LeavePeriod(Base):
    __tablename__ = "leave_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("personnel.id"), index=True)
    leave_type: Mapped[LeaveType] = mapped_column(String(50), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    starts_on: Mapped[date] = mapped_column(Date, index=True)
    ends_on: Mapped[date] = mapped_column(Date, index=True)
    days_count: Mapped[int] = mapped_column(Integer)
    initial_starts_on: Mapped[date] = mapped_column(Date)
    initial_ends_on: Mapped[date] = mapped_column(Date)
    status: Mapped[LeaveStatus] = mapped_column(String(50), default=LeaveStatus.PLANNED)
    is_frozen: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    policy_snapshot_id: Mapped[int] = mapped_column(ForeignKey("policy_snapshots.id"))
    source_request_id: Mapped[int | None] = mapped_column(ForeignKey("leave_requests.id"))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


class RoadDayPeriod(Base):
    __tablename__ = "road_day_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("personnel.id"), index=True)
    leave_period_id: Mapped[int] = mapped_column(ForeignKey("leave_periods.id"), index=True)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    days_count: Mapped[int] = mapped_column(Integer)
    destination_locality: Mapped[str] = mapped_column(String(255))
    distance_km: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


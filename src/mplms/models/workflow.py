from datetime import date
from datetime import datetime

from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from mplms.domain.enums import ConsentStatus
from mplms.domain.enums import RequestStatus
from mplms.models.base import Base
from mplms.models.base import CreatedAt
from mplms.models.base import UpdatedAt


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("personnel.id"), index=True)
    desired_start_date: Mapped[date] = mapped_column(Date)
    desired_days_count: Mapped[int] = mapped_column(Integer)
    destination_locality: Mapped[str | None] = mapped_column(String(255))
    requested_road_days: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[RequestStatus] = mapped_column(String(80), default=RequestStatus.DRAFT, index=True)
    policy_snapshot_id: Mapped[int] = mapped_column(ForeignKey("policy_snapshots.id"))
    selected_option_id: Mapped[int | None] = mapped_column(ForeignKey("request_options.id"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


class RequestOption(Base):
    __tablename__ = "request_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("leave_requests.id"), index=True)
    proposed_start_date: Mapped[date] = mapped_column(Date)
    proposed_end_date: Mapped[date] = mapped_column(Date)
    conflict_score: Mapped[int] = mapped_column(Integer, index=True)
    overlap_level: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(String(50), default="low")
    affected_people_count: Mapped[int] = mapped_column(Integer, default=0)
    explanation: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


class AffectedPersonConsent(Base):
    __tablename__ = "affected_person_consents"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("leave_requests.id"), index=True)
    affected_person_id: Mapped[int] = mapped_column(ForeignKey("personnel.id"), index=True)
    affected_leave_id: Mapped[int] = mapped_column(ForeignKey("leave_periods.id"))
    proposed_shift_days: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[ConsentStatus] = mapped_column(String(50), default=ConsentStatus.PENDING)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


class ApprovalStep(Base):
    __tablename__ = "approval_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("leave_requests.id"), index=True)
    approver_id: Mapped[int] = mapped_column(ForeignKey("personnel.id"), index=True)
    role: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    comment: Mapped[str | None] = mapped_column(String(1000))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


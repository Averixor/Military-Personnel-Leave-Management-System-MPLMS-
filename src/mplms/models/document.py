from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from mplms.models.base import Base
from mplms.models.base import CreatedAt


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("leave_requests.id"), index=True)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("personnel.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(1000))
    content_type: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[CreatedAt]


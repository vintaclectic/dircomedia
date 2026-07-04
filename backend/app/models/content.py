import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, func, Enum, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class ContentType(str, enum.Enum):
    text = "text"
    image = "image"
    video = "video"
    reel = "reel"


class ContentStatus(str, enum.Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    scheduled = "scheduled"
    posted = "posted"
    failed = "failed"


class Content(Base):
    __tablename__ = "content"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    content_type: Mapped[ContentType] = mapped_column(Enum(ContentType), nullable=False)
    status: Mapped[ContentStatus] = mapped_column(
        Enum(ContentStatus), nullable=False, default=ContentStatus.draft
    )

    title: Mapped[str] = mapped_column(String(256), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=True)
    media_url: Mapped[str] = mapped_column(String(1024), nullable=True)
    thumbnail_url: Mapped[str] = mapped_column(String(1024), nullable=True)

    prompt_used: Mapped[str] = mapped_column(Text, nullable=True)
    generation_metadata: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)

    platforms: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    platform_post_ids: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship("Project", back_populates="content")
    schedule: Mapped["Schedule"] = relationship("Schedule", back_populates="content", uselist=False)
    analytics: Mapped[list["AnalyticsSnapshot"]] = relationship("AnalyticsSnapshot", back_populates="content")

"""
Broadcast — the spine of the DirCo Broadcast Law (council decree 2026-07-04).

One row per broadcast candidate: an update/milestone/content event submitted by
the brain (or the dashboard) that fans out to social platforms. approve-first
by default — nothing posts publicly without Lord Vinta's approval.
"""
import uuid
import enum
from datetime import datetime

from sqlalchemy import String, Text, DateTime, func, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BroadcastStatus(str, enum.Enum):
    pending_approval = "pending_approval"
    approved = "approved"          # approved, queued for fan-out
    posting = "posting"            # fan-out in flight
    posted = "posted"              # every platform succeeded
    partial = "partial"            # some platforms succeeded, some failed
    failed = "failed"              # every platform failed
    vetoed = "vetoed"              # owner said no


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Idempotency: the brain's spool retries safely — same key never double-posts.
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=True, unique=True, index=True)
    # Dedupe: identical content within the dedupe window is refused.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=True, index=True)

    project_slug: Mapped[str] = mapped_column(String(64), nullable=False, default="dirco")
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="update")  # update|milestone|content
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="brain") # brain|dashboard|worklog-tap

    title: Mapped[str] = mapped_column(String(256), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=True)
    media_url: Mapped[str] = mapped_column(String(1024), nullable=True)
    content_type: Mapped[str] = mapped_column(String(16), nullable=False, default="text")  # text|image|video|reel

    platforms: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="approve-first")  # approve-first|auto

    status: Mapped[BroadcastStatus] = mapped_column(
        Enum(BroadcastStatus), nullable=False, default=BroadcastStatus.pending_approval
    )
    results: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)  # per-platform outcome
    error: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

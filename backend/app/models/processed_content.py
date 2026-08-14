"""
ProcessedContent model — tracks cross-platform content automation to prevent
duplicates (task 3JFWZQK Kick→YouTube pipeline, 2026-08-14).

Use case: Kick stream #12345 gets uploaded to YouTube as video abc123 → we record
that mapping so the next poll doesn't re-upload the same stream. Generalizes to
any source→target content flow (TikTok→YouTube, Reddit→Instagram, etc.).
"""
from sqlalchemy import Column, String, DateTime, JSON, Index
from sqlalchemy.sql import func

from app.database import Base


class ProcessedContent(Base):
    __tablename__ = "processed_content"

    id = Column(String, primary_key=True, default=lambda: f"pc_{func.gen_random_uuid()}")

    # Source (where content came from)
    source_platform = Column(String, nullable=False)  # "kick", "twitch", "tiktok"
    source_id = Column(String, nullable=False)        # platform-specific content ID
    source_url = Column(String, nullable=True)        # original content URL

    # Target (where we posted it)
    target_platform = Column(String, nullable=True)   # "youtube", "instagram", etc.
    target_id = Column(String, nullable=True)         # platform-specific post ID
    target_url = Column(String, nullable=True)        # published URL

    # Metadata (flexible JSON for platform-specific details)
    metadata = Column(JSON, nullable=True)            # titles, timestamps, tags, etc.

    # Timestamps
    processed_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes for fast duplicate checks
    __table_args__ = (
        Index("idx_source_platform_id", "source_platform", "source_id"),
        Index("idx_target_platform_id", "target_platform", "target_id"),
    )

    def __repr__(self):
        return (
            f"<ProcessedContent {self.source_platform}:{self.source_id} "
            f"→ {self.target_platform}:{self.target_id}>"
        )

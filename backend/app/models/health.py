"""Platform health history — the guardian's memory (Phase 3)."""
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PlatformHealthRecord(Base):
    __tablename__ = "platform_health"

    platform: Mapped[str] = mapped_column(String(32), primary_key=True)
    configured: Mapped[bool] = mapped_column(Boolean, nullable=True)
    live: Mapped[bool] = mapped_column(Boolean, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_alert_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

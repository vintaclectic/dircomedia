from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.models.content import Content, ContentStatus
from app.models.schedule import Schedule
from app.workers.distribution_tasks import post_now_task, schedule_post_task
from app.core.exceptions import NotFoundError

router = APIRouter()


class PostNowRequest(BaseModel):
    content_id: uuid.UUID
    platforms: Optional[list[str]] = None


class ScheduleRequest(BaseModel):
    content_id: uuid.UUID
    scheduled_at: datetime
    platforms: Optional[list[str]] = None


class DistributionOut(BaseModel):
    job_id: str
    status: str
    message: str


class ScheduleOut(BaseModel):
    id: uuid.UUID
    content_id: uuid.UUID
    scheduled_at: datetime
    is_posted: bool
    platforms: list
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/post-now", response_model=DistributionOut)
async def post_now(req: PostNowRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Content).where(Content.id == req.content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise NotFoundError("Content", str(req.content_id))

    platforms = req.platforms or content.platforms
    task = post_now_task.delay(str(content.id), platforms)

    content.status = ContentStatus.scheduled
    await db.commit()

    return DistributionOut(job_id=task.id, status="queued", message=f"Posting to {', '.join(platforms)}")


@router.post("/schedule", response_model=ScheduleOut)
async def schedule_post(req: ScheduleRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Content).where(Content.id == req.content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise NotFoundError("Content", str(req.content_id))

    platforms = req.platforms or content.platforms
    schedule = Schedule(
        project_id=content.project_id,
        content_id=content.id,
        scheduled_at=req.scheduled_at,
        platforms=platforms,
    )
    db.add(schedule)
    content.status = ContentStatus.scheduled
    await db.commit()
    await db.refresh(schedule)

    schedule_post_task.apply_async(
        args=[str(content.id), platforms],
        eta=req.scheduled_at,
    )

    return schedule


@router.get("/schedules", response_model=list[ScheduleOut])
async def list_schedules(
    upcoming_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    query = select(Schedule).order_by(Schedule.scheduled_at)
    if upcoming_only:
        query = query.where(Schedule.is_posted == False)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/health")
async def connection_health():
    """
    Connection-health rail (Phase 2/3, council decree 2026-07-04).
    Probes live in services/distribution/health.py — shared with the guardian
    beat task. An account that silently rots is a betrayal of the Cable Guy Law.
    """
    from app.services.distribution.health import check_all
    return await check_all()

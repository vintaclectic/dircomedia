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
    Connection-health rail (Phase 2, council decree 2026-07-04).
    Per platform: {configured, live} — live=None means no cheap probe exists.
    An account that silently rots is a betrayal of the Cable Guy Law.
    """
    import asyncio
    import httpx
    from app.config import settings as cfg
    from app.services.distribution.platforms.discord import DiscordClient
    from app.services.distribution.platforms.telegram import TelegramClient
    from app.services.distribution.platforms.youtube import YouTubeClient
    from app.services.storage import r2 as r2_storage

    async def twitter_health():
        configured = all([
            cfg.twitter_api_key, cfg.twitter_api_secret,
            cfg.twitter_access_token, cfg.twitter_access_secret,
        ])
        if not configured:
            return {"configured": False, "live": None}
        try:
            from app.services.distribution.platforms.twitter import TwitterClient
            tw = TwitterClient()
            url = "https://api.twitter.com/2/users/me"
            headers = tw._oauth_headers("GET", url)
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, headers=headers)
                return {"configured": True, "live": r.status_code == 200}
        except Exception:
            return {"configured": True, "live": False}

    async def reddit_health():
        configured = all([
            cfg.reddit_client_id, cfg.reddit_client_secret,
            cfg.reddit_username, cfg.reddit_password,
        ])
        if not configured:
            return {"configured": False, "live": None}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    "https://www.reddit.com/api/v1/access_token",
                    auth=(cfg.reddit_client_id, cfg.reddit_client_secret),
                    data={
                        "grant_type": "password",
                        "username": cfg.reddit_username,
                        "password": cfg.reddit_password,
                    },
                    headers={"User-Agent": "dircomedia-health/1.0"},
                )
                return {"configured": True, "live": r.status_code == 200 and "access_token" in r.json()}
        except Exception:
            return {"configured": True, "live": False}

    async def instagram_health():
        if not cfg.instagram_access_token:
            return {"configured": False, "live": None}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://graph.facebook.com/v21.0/me",
                    params={"access_token": cfg.instagram_access_token},
                )
                return {"configured": True, "live": r.status_code == 200}
        except Exception:
            return {"configured": True, "live": False}

    async def tiktok_health():
        configured = bool(cfg.tiktok_client_key and cfg.tiktok_access_token)
        return {"configured": configured, "live": None}  # no cheap probe

    results = await asyncio.gather(
        twitter_health(),
        reddit_health(),
        instagram_health(),
        tiktok_health(),
        DiscordClient().health(),
        TelegramClient().health(),
        YouTubeClient().health(),
        r2_storage.health(),
        return_exceptions=True,
    )
    names = ["twitter", "reddit", "instagram", "tiktok", "discord", "telegram", "youtube", "r2_storage"]
    return {
        name: (r if isinstance(r, dict) else {"configured": None, "live": False, "error": str(r)})
        for name, r in zip(names, results)
    }

"""
Broadcast Spine API — council decree 2026-07-04, Phase 1.

The brain (vintinuum-api) submits broadcast candidates here; the dashboard /
Android / extension approve or veto them; the fan-out worker posts to every
connected platform.

Circuit breakers (THE ACCOUNTS ARE THE ASSET):
  - kill switch: BROADCAST_KILL_SWITCH=true → nothing fans out, period
  - daily cap: at most BROADCAST_DAILY_CAP fan-outs per UTC day
  - dedupe: identical content (project+title+body) refused within
    BROADCAST_DEDUPE_HOURS
  - idempotency: same idempotency_key returns the existing row, never a double
"""
import hashlib
import uuid
from datetime import datetime, timezone, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.broadcast import Broadcast, BroadcastStatus
from app.workers.broadcast_tasks import broadcast_fanout_task

router = APIRouter()

TEXT_CAPABLE = ["twitter", "reddit", "discord", "telegram", "bluesky"]
MEDIA_CAPABLE = ["twitter", "reddit", "discord", "telegram", "bluesky", "instagram", "tiktok", "youtube"]
FANNED_OUT = [BroadcastStatus.posting, BroadcastStatus.posted, BroadcastStatus.partial]


class BroadcastIn(BaseModel):
    project: str = Field(default="dirco", max_length=64)
    kind: str = Field(default="update")                 # update|milestone|content
    title: Optional[str] = Field(default=None, max_length=256)
    body: Optional[str] = None
    media_url: Optional[str] = None
    content_type: str = Field(default="text")           # text|image|video|reel
    platforms: Optional[list[str]] = None               # None/["all"] → sensible default
    mode: str = Field(default="approve-first")          # approve-first|auto
    idempotency_key: Optional[str] = Field(default=None, max_length=128)
    source: str = Field(default="brain", max_length=64)


class BroadcastOut(BaseModel):
    id: uuid.UUID
    project_slug: str
    kind: str
    source: str
    title: Optional[str]
    body: Optional[str]
    media_url: Optional[str]
    content_type: str
    platforms: list
    mode: str
    status: BroadcastStatus
    results: Optional[dict]
    error: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


def _resolve_platforms(req: BroadcastIn) -> list[str]:
    if not req.platforms or req.platforms == ["all"]:
        if req.media_url and req.content_type in ("video", "reel"):
            return MEDIA_CAPABLE
        if req.media_url:
            # image: everything except the video-only platforms
            return [p for p in MEDIA_CAPABLE if p not in ("tiktok", "youtube")]
        return TEXT_CAPABLE
    return [p for p in req.platforms if p in MEDIA_CAPABLE]


def _content_hash(project: str, title: Optional[str], body: Optional[str]) -> str:
    raw = f"{project}|{title or ''}|{body or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def _fanout_guard(db: AsyncSession) -> None:
    """Circuit breakers — raise before anything is allowed to fan out."""
    if settings.broadcast_kill_switch:
        raise HTTPException(status_code=423, detail="Broadcast kill switch is engaged.")
    day_start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
    result = await db.execute(
        select(func.count()).select_from(Broadcast).where(
            Broadcast.status.in_(FANNED_OUT),
            Broadcast.created_at >= day_start,
        )
    )
    if (result.scalar() or 0) >= settings.broadcast_daily_cap:
        raise HTTPException(
            status_code=429,
            detail=f"Daily broadcast cap ({settings.broadcast_daily_cap}) reached. The accounts are the asset.",
        )


async def _dispatch(broadcast: Broadcast, db: AsyncSession) -> None:
    await _fanout_guard(db)
    broadcast.status = BroadcastStatus.approved
    await db.commit()
    broadcast_fanout_task.delay(str(broadcast.id))


@router.post("/", response_model=BroadcastOut)
async def submit_broadcast(req: BroadcastIn, db: AsyncSession = Depends(get_db)):
    if not (req.title or req.body):
        raise HTTPException(status_code=422, detail="A broadcast needs a title or a body.")

    # Idempotency: replaying the same spool line returns the existing row.
    if req.idempotency_key:
        existing = await db.execute(
            select(Broadcast).where(Broadcast.idempotency_key == req.idempotency_key)
        )
        row = existing.scalar_one_or_none()
        if row:
            return row

    # Dedupe: identical content within the window is refused (unless vetoed/failed).
    chash = _content_hash(req.project, req.title, req.body)
    window_start = datetime.now(timezone.utc).timestamp() - settings.broadcast_dedupe_hours * 3600
    dup = await db.execute(
        select(Broadcast).where(
            Broadcast.content_hash == chash,
            Broadcast.status.notin_([BroadcastStatus.vetoed, BroadcastStatus.failed]),
            Broadcast.created_at >= datetime.fromtimestamp(window_start, tz=timezone.utc),
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Identical content already broadcast within the dedupe window.")

    broadcast = Broadcast(
        idempotency_key=req.idempotency_key,
        content_hash=chash,
        project_slug=req.project,
        kind=req.kind,
        source=req.source,
        title=req.title,
        body=req.body,
        media_url=req.media_url,
        content_type=req.content_type,
        platforms=_resolve_platforms(req),
        mode=req.mode,
        status=BroadcastStatus.pending_approval,
    )
    db.add(broadcast)
    await db.commit()
    await db.refresh(broadcast)

    if req.mode == "auto":
        await _dispatch(broadcast, db)
        await db.refresh(broadcast)

    return broadcast


@router.get("/pending", response_model=list[BroadcastOut])
async def list_pending(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Broadcast)
        .where(Broadcast.status == BroadcastStatus.pending_approval)
        .order_by(Broadcast.created_at.desc())
    )
    return result.scalars().all()


@router.get("/", response_model=list[BroadcastOut])
async def list_broadcasts(limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Broadcast).order_by(Broadcast.created_at.desc()).limit(min(limit, 200))
    )
    return result.scalars().all()


@router.get("/{broadcast_id}", response_model=BroadcastOut)
async def get_broadcast(broadcast_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Broadcast not found.")
    return row


@router.post("/{broadcast_id}/approve", response_model=BroadcastOut)
async def approve_broadcast(broadcast_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Broadcast not found.")
    if row.status != BroadcastStatus.pending_approval:
        raise HTTPException(status_code=409, detail=f"Broadcast is {row.status.value}, not pending approval.")
    await _dispatch(row, db)
    await db.refresh(row)
    return row


@router.post("/{broadcast_id}/veto", response_model=BroadcastOut)
async def veto_broadcast(broadcast_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Broadcast not found.")
    if row.status in FANNED_OUT:
        raise HTTPException(status_code=409, detail="Too late — broadcast already fanned out.")
    row.status = BroadcastStatus.vetoed
    await db.commit()
    await db.refresh(row)
    return row

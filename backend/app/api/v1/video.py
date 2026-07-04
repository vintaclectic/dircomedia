from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import uuid
from typing import Optional

from app.database import get_db
from app.models.content import Content, ContentType, ContentStatus
from app.models.project import Project
from app.services.video_pipeline.processor import VideoProcessor
from app.workers.video_tasks import process_recording_task, generate_hype_clip_task
from app.core.exceptions import NotFoundError
from sqlalchemy import select

router = APIRouter()
processor = VideoProcessor()


class HypeClipRequest(BaseModel):
    project_slug: str
    description: str
    duration: int = 30
    style: str = "cinematic"
    platforms: list[str] = ["tiktok", "instagram"]


class VideoJobOut(BaseModel):
    job_id: str
    status: str
    content_id: Optional[uuid.UUID] = None
    message: str


@router.post("/process-recording", response_model=VideoJobOut)
async def process_recording(
    project_slug: str = Form(...),
    platforms: str = Form("tiktok,instagram"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Accept a raw screen recording and queue cinematic wrapping."""
    project_result = await db.execute(select(Project).where(Project.slug == project_slug))
    project = project_result.scalar_one_or_none()
    if not project:
        raise NotFoundError("Project", project_slug)

    import os, aiofiles
    from app.config import settings

    os.makedirs(settings.media_upload_dir, exist_ok=True)
    upload_path = f"{settings.media_upload_dir}/{uuid.uuid4()}_{file.filename}"
    async with aiofiles.open(upload_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    content_record = Content(
        project_id=project.id,
        content_type=ContentType.video,
        status=ContentStatus.draft,
        platforms=platforms.split(","),
    )
    db.add(content_record)
    await db.commit()
    await db.refresh(content_record)

    task = process_recording_task.delay(
        str(content_record.id), str(project.id), upload_path, project_slug
    )

    return VideoJobOut(
        job_id=task.id,
        status="queued",
        content_id=content_record.id,
        message="Recording queued for cinematic processing",
    )


@router.post("/hype-clip", response_model=VideoJobOut)
async def generate_hype_clip(req: HypeClipRequest, db: AsyncSession = Depends(get_db)):
    """Generate a standalone hype/promo clip from a project description."""
    project_result = await db.execute(select(Project).where(Project.slug == req.project_slug))
    project = project_result.scalar_one_or_none()
    if not project:
        raise NotFoundError("Project", req.project_slug)

    content_record = Content(
        project_id=project.id,
        content_type=ContentType.reel,
        status=ContentStatus.draft,
        body=req.description,
        platforms=req.platforms,
    )
    db.add(content_record)
    await db.commit()
    await db.refresh(content_record)

    task = generate_hype_clip_task.delay(
        str(content_record.id), req.description, req.project_slug, req.duration, req.style
    )

    return VideoJobOut(
        job_id=task.id,
        status="queued",
        content_id=content_record.id,
        message="Hype clip generation queued",
    )


@router.get("/job/{job_id}", response_model=VideoJobOut)
async def get_job_status(job_id: str):
    from app.workers.celery_app import celery_app
    result = celery_app.AsyncResult(job_id)
    return VideoJobOut(
        job_id=job_id,
        status=result.status.lower(),
        message=str(result.result) if result.ready() else "Processing...",
    )

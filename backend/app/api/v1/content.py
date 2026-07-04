from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.models.content import Content, ContentType, ContentStatus
from app.models.project import Project
from app.services.content_engine.generator import ContentGenerator
from app.core.exceptions import NotFoundError

router = APIRouter()
generator = ContentGenerator()


class GenerateRequest(BaseModel):
    project_slug: str
    content_type: ContentType
    topic: str
    platforms: list[str] = ["twitter", "instagram"]
    auto_approve: bool = True


class ContentOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    content_type: ContentType
    status: ContentStatus
    title: Optional[str]
    body: Optional[str]
    media_url: Optional[str]
    platforms: list
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/generate", response_model=ContentOut)
async def generate_content(req: GenerateRequest, db: AsyncSession = Depends(get_db)):
    project_result = await db.execute(select(Project).where(Project.slug == req.project_slug))
    project = project_result.scalar_one_or_none()
    if not project:
        raise NotFoundError("Project", req.project_slug)

    result = await generator.generate_text(
        project_slug=req.project_slug,
        topic=req.topic,
        platforms=req.platforms,
    )

    status = ContentStatus.approved if req.auto_approve else ContentStatus.pending_approval
    content = Content(
        project_id=project.id,
        content_type=req.content_type,
        status=status,
        title=result.get("title"),
        body=result.get("body"),
        platforms=req.platforms,
        prompt_used=result.get("prompt"),
        generation_metadata=result.get("metadata", {}),
    )
    db.add(content)
    await db.commit()
    await db.refresh(content)
    return content


@router.get("/", response_model=list[ContentOut])
async def list_content(
    project_slug: Optional[str] = None,
    status: Optional[ContentStatus] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    query = select(Content).order_by(Content.created_at.desc()).limit(limit)
    if project_slug:
        project_result = await db.execute(select(Project).where(Project.slug == project_slug))
        project = project_result.scalar_one_or_none()
        if project:
            query = query.where(Content.project_id == project.id)
    if status:
        query = query.where(Content.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{content_id}", response_model=ContentOut)
async def get_content(content_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise NotFoundError("Content", str(content_id))
    return content


@router.patch("/{content_id}/approve", response_model=ContentOut)
async def approve_content(content_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise NotFoundError("Content", str(content_id))
    content.status = ContentStatus.approved
    await db.commit()
    await db.refresh(content)
    return content

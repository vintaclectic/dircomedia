from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid
from datetime import datetime

from app.database import get_db
from app.models.project import Project
from app.core.exceptions import NotFoundError

router = APIRouter()


class ProjectOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=list[ProjectOut])
async def list_projects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).order_by(Project.name))
    return result.scalars().all()


@router.get("/{slug}", response_model=ProjectOut)
async def get_project(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.slug == slug))
    project = result.scalar_one_or_none()
    if not project:
        raise NotFoundError("Project", slug)
    return project


@router.post("/seed")
async def seed_projects(db: AsyncSession = Depends(get_db)):
    """Seed the default DirCo projects."""
    projects = [
        {"slug": "dirco", "name": "DirCo", "description": "Umbrella company brand"},
        {"slug": "dirhaven-rp", "name": "DirHaven RP", "description": "FiveM roleplay server"},
        {"slug": "dirhaven-app", "name": "DirHaven App", "description": "Mobile/web companion app"},
        {"slug": "dirmegle", "name": "DirMegle", "description": "Anonymous social discovery platform"},
        {"slug": "medaled", "name": "Medaled", "description": "Achievement and recognition platform"},
        {"slug": "agentis", "name": "Agentis", "description": "AI agent infrastructure"},
        {"slug": "vintinuum", "name": "Vintinuum", "description": "Living cognitive AI organism"},
    ]
    for p in projects:
        existing = await db.execute(select(Project).where(Project.slug == p["slug"]))
        if not existing.scalar_one_or_none():
            db.add(Project(**p))
    await db.commit()
    return {"seeded": len(projects)}

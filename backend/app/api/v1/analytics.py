from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
import uuid
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.models.analytics import AnalyticsSnapshot
from app.models.project import Project
from app.services.analytics.collector import AnalyticsCollector
from app.services.analytics.analyzer import StrategyAnalyzer

router = APIRouter()
collector = AnalyticsCollector()
analyzer = StrategyAnalyzer()


class SnapshotOut(BaseModel):
    id: uuid.UUID
    platform: str
    impressions: int
    likes: int
    comments: int
    shares: int
    engagement_rate: float
    captured_at: datetime

    class Config:
        from_attributes = True


class ProjectSummary(BaseModel):
    project_slug: str
    total_impressions: int
    total_likes: int
    avg_engagement_rate: float
    top_platform: str
    content_count: int


class StrategyInsight(BaseModel):
    project_slug: str
    insights: list[str]
    recommended_content_types: list[str]
    recommended_posting_times: dict
    best_platforms: list[str]


@router.post("/collect/{project_slug}")
async def collect_analytics(project_slug: str, db: AsyncSession = Depends(get_db)):
    """Trigger analytics collection for a project across all platforms."""
    project_result = await db.execute(select(Project).where(Project.slug == project_slug))
    project = project_result.scalar_one_or_none()
    if not project:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Project", project_slug)

    snapshots = await collector.collect_all(project_slug, str(project.id))
    for s in snapshots:
        db.add(AnalyticsSnapshot(**s))
    await db.commit()

    return {"collected": len(snapshots)}


@router.get("/summary/{project_slug}", response_model=ProjectSummary)
async def get_project_summary(project_slug: str, db: AsyncSession = Depends(get_db)):
    project_result = await db.execute(select(Project).where(Project.slug == project_slug))
    project = project_result.scalar_one_or_none()
    if not project:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Project", project_slug)

    result = await db.execute(
        select(
            func.sum(AnalyticsSnapshot.impressions).label("total_impressions"),
            func.sum(AnalyticsSnapshot.likes).label("total_likes"),
            func.avg(AnalyticsSnapshot.engagement_rate).label("avg_engagement"),
            func.count(AnalyticsSnapshot.id).label("count"),
        ).where(AnalyticsSnapshot.project_id == project.id)
    )
    row = result.one()

    top_platform_result = await db.execute(
        select(AnalyticsSnapshot.platform, func.sum(AnalyticsSnapshot.impressions).label("total"))
        .where(AnalyticsSnapshot.project_id == project.id)
        .group_by(AnalyticsSnapshot.platform)
        .order_by(func.sum(AnalyticsSnapshot.impressions).desc())
        .limit(1)
    )
    top = top_platform_result.one_or_none()

    return ProjectSummary(
        project_slug=project_slug,
        total_impressions=int(row.total_impressions or 0),
        total_likes=int(row.total_likes or 0),
        avg_engagement_rate=float(row.avg_engagement or 0.0),
        top_platform=top.platform if top else "none",
        content_count=int(row.count or 0),
    )


@router.get("/strategy/{project_slug}", response_model=StrategyInsight)
async def get_strategy(project_slug: str, db: AsyncSession = Depends(get_db)):
    """Analyze performance data and return content strategy recommendations."""
    project_result = await db.execute(select(Project).where(Project.slug == project_slug))
    project = project_result.scalar_one_or_none()
    if not project:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Project", project_slug)

    snapshots_result = await db.execute(
        select(AnalyticsSnapshot).where(AnalyticsSnapshot.project_id == project.id).limit(200)
    )
    snapshots = snapshots_result.scalars().all()
    insights = await analyzer.analyze(project_slug, snapshots)
    return StrategyInsight(project_slug=project_slug, **insights)

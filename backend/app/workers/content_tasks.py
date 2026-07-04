import asyncio
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, name="app.workers.content_tasks.generate_content", max_retries=3)
def generate_content_task(self, project_slug: str, topic: str, content_type: str, platforms: list[str]):
    """Async content generation task."""
    async def _run():
        from app.services.content_engine.generator import ContentGenerator
        from app.database import AsyncSessionLocal
        from app.models.content import Content, ContentType, ContentStatus
        from app.models.project import Project
        from sqlalchemy import select

        generator = ContentGenerator()
        result = await generator.generate_text(project_slug, topic, platforms)

        async with AsyncSessionLocal() as db:
            project_result = await db.execute(select(Project).where(Project.slug == project_slug))
            project = project_result.scalar_one_or_none()
            if project:
                content = Content(
                    project_id=project.id,
                    content_type=ContentType(content_type),
                    status=ContentStatus.approved,
                    title=result.get("title"),
                    body=result.get("body"),
                    platforms=platforms,
                    prompt_used=result.get("prompt"),
                    generation_metadata=result.get("metadata", {}),
                )
                db.add(content)
                await db.commit()
                return str(content.id)
        return None

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="app.workers.content_tasks.collect_all_analytics")
def collect_all_analytics():
    """Periodic task: collect analytics for all projects."""
    async def _run():
        from app.services.analytics.collector import AnalyticsCollector
        from app.database import AsyncSessionLocal
        from app.models.project import Project
        from app.models.analytics import AnalyticsSnapshot
        from sqlalchemy import select

        collector = AnalyticsCollector()
        async with AsyncSessionLocal() as db:
            projects_result = await db.execute(select(Project))
            projects = projects_result.scalars().all()
            total = 0
            for project in projects:
                snapshots = await collector.collect_all(project.slug, str(project.id))
                for s in snapshots:
                    db.add(AnalyticsSnapshot(**s))
                total += len(snapshots)
            await db.commit()
        return {"collected": total}

    return asyncio.get_event_loop().run_until_complete(_run())

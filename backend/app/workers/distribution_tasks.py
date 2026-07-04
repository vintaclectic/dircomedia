import asyncio
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, name="app.workers.distribution_tasks.post_now", max_retries=3)
def post_now_task(self, content_id: str, platforms: list[str]):
    async def _run():
        from app.services.distribution.scheduler import DistributionScheduler
        from app.database import AsyncSessionLocal
        from app.models.content import Content, ContentStatus
        from sqlalchemy import select
        import uuid

        scheduler = DistributionScheduler()

        async with AsyncSessionLocal() as db:
            content_result = await db.execute(
                select(Content).where(Content.id == uuid.UUID(content_id))
            )
            content = content_result.scalar_one_or_none()
            if not content:
                return {"error": "Content not found"}

            results = await scheduler.post(
                platforms=platforms,
                body=content.body or content.title or "",
                media_url=content.media_url,
                content_type=content.content_type.value,
                project_slug="",
            )

            post_ids = {}
            all_failed = True
            for platform, result in results.items():
                if "error" not in result:
                    all_failed = False
                    post_ids[platform] = result.get("id") or result.get("post_id") or result.get("publish_id")

            content.platform_post_ids = post_ids
            content.status = ContentStatus.failed if all_failed else ContentStatus.posted
            await db.commit()

        return results

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, name="app.workers.distribution_tasks.schedule_post", max_retries=3)
def schedule_post_task(self, content_id: str, platforms: list[str]):
    """This task is called at the scheduled time via Celery ETA."""
    return post_now_task(content_id, platforms)


@celery_app.task(name="app.workers.distribution_tasks.process_due_schedules")
def process_due_schedules():
    """Periodic beat task: process any overdue scheduled posts."""
    async def _run():
        from app.database import AsyncSessionLocal
        from app.models.schedule import Schedule
        from sqlalchemy import select
        from datetime import datetime, timezone

        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(Schedule).where(
                    Schedule.is_posted == False,
                    Schedule.failed == False,
                    Schedule.scheduled_at <= now,
                )
            )
            due = result.scalars().all()
            for schedule in due:
                post_now_task.delay(str(schedule.content_id), schedule.platforms)
            return {"processed": len(due)}

    return asyncio.get_event_loop().run_until_complete(_run())

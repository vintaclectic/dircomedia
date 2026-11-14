import asyncio
from app.workers.celery_app import celery_app


def _run_async(coro):
    """Run a coroutine from a sync Celery task.

    asyncio.get_event_loop() RAISES on Python 3.12 in a thread with no current
    loop, which is where Celery's prefork pool runs tasks: every approved
    broadcast failed with "There is no current event loop in thread
    'MainThread'" and sat at status=approved (68 rows, 2026-11-14). asyncio.run()
    gives each task its own loop; the pooled async engine is disposed at the end
    so no connection outlives the loop it was opened on.
    """
    async def _wrapped():
        from app.database import engine
        try:
            return await coro
        finally:
            await engine.dispose()
    return asyncio.run(_wrapped())


@celery_app.task(bind=True, name="app.workers.video_tasks.process_recording", max_retries=2)
def process_recording_task(
    self, content_id: str, project_id: str, file_path: str, project_slug: str
):
    async def _run():
        from app.services.video_pipeline.processor import VideoProcessor
        from app.database import AsyncSessionLocal
        from app.models.content import Content, ContentStatus
        from sqlalchemy import select
        import uuid

        processor = VideoProcessor()
        result = await processor.process_recording(content_id, project_id, file_path, project_slug)

        async with AsyncSessionLocal() as db:
            content_result = await db.execute(
                select(Content).where(Content.id == uuid.UUID(content_id))
            )
            content = content_result.scalar_one_or_none()
            if content:
                content.media_url = result.get("output_url")
                content.status = ContentStatus.approved
                await db.commit()

        return result

    try:
        return _run_async(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)


@celery_app.task(bind=True, name="app.workers.video_tasks.generate_hype_clip", max_retries=2)
def generate_hype_clip_task(
    self, content_id: str, description: str, project_slug: str, duration: int, style: str
):
    async def _run():
        from app.services.video_pipeline.processor import VideoProcessor
        from app.database import AsyncSessionLocal
        from app.models.content import Content, ContentStatus
        from sqlalchemy import select
        import uuid

        processor = VideoProcessor()
        result = await processor.generate_hype_clip(
            content_id, description, project_slug, duration, style
        )

        async with AsyncSessionLocal() as db:
            content_result = await db.execute(
                select(Content).where(Content.id == uuid.UUID(content_id))
            )
            content = content_result.scalar_one_or_none()
            if content:
                content.media_url = result.get("output_url")
                content.status = ContentStatus.approved
                await db.commit()

        return result

    try:
        return _run_async(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)

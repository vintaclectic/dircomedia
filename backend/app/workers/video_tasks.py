import asyncio
from app.workers.celery_app import celery_app


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
        return asyncio.get_event_loop().run_until_complete(_run())
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
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)

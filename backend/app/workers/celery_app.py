from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "dircomedia",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.content_tasks",
        "app.workers.video_tasks",
        "app.workers.distribution_tasks",
        "app.workers.broadcast_tasks",
        "app.workers.guardian_tasks",
        "app.workers.persistence_tasks",
        "app.workers.kick_youtube_pipeline",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.workers.video_tasks.*": {"queue": "video"},
        "app.workers.distribution_tasks.*": {"queue": "distribution"},
        "app.workers.broadcast_tasks.*": {"queue": "distribution"},
        "app.workers.guardian_tasks.*": {"queue": "distribution"},
        "app.workers.persistence_tasks.*": {"queue": "content"},
        "app.workers.content_tasks.*": {"queue": "content"},
        "kick_youtube_pipeline.*": {"queue": "video"},  # heavy downloads + uploads
    },
    beat_schedule={
        "collect-analytics-hourly": {
            "task": "app.workers.content_tasks.collect_all_analytics",
            "schedule": 3600.0,
        },
        "process-scheduled-posts": {
            "task": "app.workers.distribution_tasks.process_due_schedules",
            "schedule": 60.0,
        },
        # ── Phase 3 guardians (council decree 2026-07-04) ──
        "guardian-health-watch": {
            "task": "app.workers.guardian_tasks.platform_health_check",
            "schedule": crontab(minute=0, hour="*/6"),  # every 6h
        },
        # ── OAuth token renewal (YH9AE4D, 2026-08-12) ──
        # Every 6h, offset 30 min off the health check so the two guardians
        # never contend for the same provider rate limits in the same minute.
        "guardian-oauth-token-refresh": {
            "task": "app.workers.guardian_tasks.refresh_expiring_tokens",
            "schedule": crontab(minute=30, hour="*/6"),
        },
        "guardian-instagram-token-refresh": {
            "task": "app.workers.guardian_tasks.refresh_instagram_token",
            "schedule": crontab(minute=0, hour=8, day_of_week=1),  # Mondays 08:00 UTC
        },
        "persistence-engine-daily": {
            "task": "app.workers.persistence_tasks.run_persistence_engine",
            "schedule": crontab(minute=0, hour=14),  # daily 14:00 UTC
        },
        # ── Kick → YouTube automation (task 3JFWZQK, 2026-08-14) ──
        "kick-youtube-pipeline": {
            "task": "kick_youtube_pipeline.poll_and_upload",
            "schedule": 1800.0,  # every 30 min — catches ended streams fast
        },
    },
)

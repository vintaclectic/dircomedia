from celery import Celery
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
        "app.workers.content_tasks.*": {"queue": "content"},
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
    },
)

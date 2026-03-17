from celery import Celery
from app.config import settings

app = Celery(
    "juke_marketing",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

app.config_from_object({
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "timezone": "UTC",
    "enable_utc": True,
    "beat_schedule": {
        "poll-inbox": {
            "task": "app.tasks.pipeline.poll_and_queue",
            "schedule": settings.IMAP_POLL_INTERVAL_SECONDS,
        },
    },
})

# Auto-discover tasks
app.autodiscover_tasks(["app.tasks"])

from celery import Celery

from app.config import settings

celery_app = Celery(
    "trustrag",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.ingestion_tasks",
        "app.workers.connector_tasks",
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
)

celery_app.autodiscover_tasks(["app.workers"])

# Beat schedule — periodic connector sync check
celery_app.conf.beat_schedule = {
    "sync-all-connectors": {
        "task": "app.workers.connector_tasks.sync_all_connectors_task",
        "schedule": 3600.0,  # every hour
    },
}

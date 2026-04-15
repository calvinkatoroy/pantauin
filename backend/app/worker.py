from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "pantauind",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.scan_tasks",
        "app.tasks.tld_sweep_tasks",
        "app.tasks.schedule_tasks",
        "app.tasks.retention_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Jakarta",
    enable_utc=True,
    worker_prefetch_multiplier=1,  # scan jobs are long-running, don't prefetch
    task_acks_late=True,           # ack after task completes
    beat_schedule={
        "dispatch-due-schedules": {
            "task": "schedule_tasks.dispatch_due_schedules",
            "schedule": 60.0,  # check every 60 seconds
        },
        "purge-old-data": {
            "task": "retention_tasks.purge_old_data",
            "schedule": 86400.0,  # run once daily (seconds)
        },
    },
    beat_schedule_filename="/app/celerybeat-schedule",
)

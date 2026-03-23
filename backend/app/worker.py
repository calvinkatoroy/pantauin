from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "pantauin",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.scan_tasks", "app.tasks.tld_sweep_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Jakarta",
    enable_utc=True,
    worker_prefetch_multiplier=1,  # scan jobs are long-running, don't prefetch
    task_acks_late=True,           # ack after task completes
)

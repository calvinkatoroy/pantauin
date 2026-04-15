import asyncio
import logging

from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="scan_tasks.run_scan", bind=True, max_retries=0)
def run_scan(self, scan_id: str, domain: str) -> None:
    from app.core.deps import engine
    from app.scanner.pipeline import run_pipeline
    engine.sync_engine.dispose(close=False)
    asyncio.run(run_pipeline(scan_id, domain))

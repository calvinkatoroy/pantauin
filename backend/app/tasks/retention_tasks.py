"""
Celery task: purge old scan records and their evidence files.

Runs daily (configured in worker.py beat_schedule).
Retention windows are controlled by:
  EVIDENCE_RETENTION_DAYS  (default 90)  - delete evidence files older than N days
  SCAN_RETENTION_DAYS      (default 365) - delete scan records older than N days

For S3/R2 deployments, evidence objects are deleted via the storage abstraction.
For local deployments, evidence directories are deleted from disk.
"""
import asyncio
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete

from app.core.config import settings
from app.core.deps import AsyncSessionLocal
from app.core.storage import delete_evidence_prefix
from app.models.scan import ScanJob
from app.worker import celery_app

logger = logging.getLogger(__name__)


async def _purge_old_scans() -> dict:
    """
    Delete ScanJob rows (and cascade to findings/module_statuses) older than
    SCAN_RETENTION_DAYS. Also purge their evidence files/objects.
    Returns a summary dict.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.scan_retention_days)
    deleted_scans = 0
    deleted_evidence = 0

    async with AsyncSessionLocal() as db:
        # Fetch IDs of root scans to delete (children cascade from parent delete)
        result = await db.execute(
            select(ScanJob.id, ScanJob.domain)
            .where(
                ScanJob.created_at < cutoff,
                ScanJob.parent_id.is_(None),
            )
        )
        old_scans = result.all()

        for scan_id, domain in old_scans:
            # Delete evidence for this scan
            prefix = f"{scan_id}/"
            s3_deleted = delete_evidence_prefix(prefix)
            if not s3_deleted:
                # Local mode - remove evidence directory
                local_dir = os.path.join(settings.evidence_dir, scan_id)
                if os.path.isdir(local_dir):
                    try:
                        shutil.rmtree(local_dir)
                        deleted_evidence += 1
                    except Exception as exc:
                        logger.warning("Could not delete evidence dir %s: %s", local_dir, exc)
            else:
                deleted_evidence += 1

        if old_scans:
            old_ids = [row[0] for row in old_scans]
            # SQLAlchemy bulk delete - cascades to children via FK
            await db.execute(
                delete(ScanJob).where(ScanJob.id.in_(old_ids))
            )
            await db.commit()
            deleted_scans = len(old_ids)
            logger.info(
                "Retention: deleted %d scans older than %d days",
                deleted_scans,
                settings.scan_retention_days,
            )

    return {"deleted_scans": deleted_scans, "deleted_evidence_dirs": deleted_evidence}


async def _purge_old_evidence_only() -> dict:
    """
    Purge evidence files older than EVIDENCE_RETENTION_DAYS even if the scan
    record is still present. This handles large screenshot accumulation where
    the scan record itself is kept longer.

    Local mode only: walks evidence_dir, removes subdirs with mtime > threshold.
    S3 mode: not applied here - rely on S3 lifecycle policies or the scan-level
    deletion above.
    """
    if not os.path.isdir(settings.evidence_dir):
        return {"purged_dirs": 0}

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.evidence_retention_days)
    purged = 0

    for entry in os.scandir(settings.evidence_dir):
        if not entry.is_dir():
            continue
        try:
            mtime = datetime.utcfromtimestamp(entry.stat().st_mtime)
            if mtime < cutoff:
                shutil.rmtree(entry.path)
                purged += 1
                logger.debug("Purged stale evidence dir: %s", entry.path)
        except Exception as exc:
            logger.warning("Could not stat/remove %s: %s", entry.path, exc)

    if purged:
        logger.info("Evidence retention: purged %d stale evidence directories", purged)

    return {"purged_dirs": purged}


@celery_app.task(name="retention_tasks.purge_old_data")
def purge_old_data():
    """
    Celery task: purge old scan records and evidence files.
    Scheduled daily by Celery beat.
    """
    from app.core.deps import engine
    engine.sync_engine.dispose(close=False)
    result = asyncio.run(_purge_old_scans())
    engine.sync_engine.dispose(close=False)
    evidence_result = asyncio.run(_purge_old_evidence_only())
    summary = {**result, **evidence_result}
    logger.info("Retention task complete: %s", summary)
    return summary

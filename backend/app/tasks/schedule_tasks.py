import asyncio
import logging
from datetime import datetime, timedelta

from app.worker import celery_app

logger = logging.getLogger(__name__)

_INTERVAL_DELTA: dict[str, timedelta] = {
    "daily":   timedelta(days=1),
    "weekly":  timedelta(weeks=1),
    "monthly": timedelta(days=30),
}


async def _dispatch_due_async() -> None:
    from sqlalchemy import select
    from app.core.deps import AsyncSessionLocal
    from app.core.config import settings
    from app.models.scan import ScanJob, ModuleStatus, ScanSchedule

    now = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ScanSchedule).where(
                ScanSchedule.enabled.is_(True),
                ScanSchedule.next_run_at <= now,
            )
        )
        due = result.scalars().all()

        for schedule in due:
            try:
                from app.tasks.scan_tasks import run_scan
                from app.tasks.tld_sweep_tasks import run_tld_sweep

                is_sweep = schedule.domain.startswith(".")
                active_modules = [
                    "dork_sweep", "page_crawl", "header_probe",
                    "path_probe", "cms_detect",
                ]
                if settings.shodan_api_key:
                    active_modules.append("shodan_probe")

                if is_sweep:
                    job = ScanJob(domain=schedule.domain, status="pending", scan_type="tld_sweep")
                    db.add(job)
                    await db.flush()
                    db.add(ModuleStatus(scan_job_id=job.id, module="dork_sweep", status="pending"))
                    await db.commit()
                    await db.refresh(job)
                    task = run_tld_sweep.delay(job.id, schedule.domain)
                    job.celery_task_id = task.id
                else:
                    job = ScanJob(domain=schedule.domain, status="pending", scan_type="single")
                    db.add(job)
                    await db.flush()
                    for module in active_modules:
                        db.add(ModuleStatus(scan_job_id=job.id, module=module, status="pending"))
                    await db.commit()
                    await db.refresh(job)
                    task = run_scan.delay(job.id, schedule.domain)
                    job.celery_task_id = task.id

                # Advance schedule to next run
                schedule.last_run_at = now
                schedule.next_run_at = now + _INTERVAL_DELTA[schedule.interval]
                await db.commit()

                logger.info(
                    "Scheduled scan dispatched: domain=%s interval=%s scan_id=%s",
                    schedule.domain, schedule.interval, job.id,
                )
            except Exception as exc:
                logger.exception(
                    "Failed to dispatch scheduled scan for domain=%s: %s",
                    schedule.domain, exc,
                )


@celery_app.task(name="schedule_tasks.dispatch_due_schedules")
def dispatch_due_schedules() -> None:
    asyncio.run(_dispatch_due_async())

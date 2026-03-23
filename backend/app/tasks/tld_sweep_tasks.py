"""
Celery task for TLD sweep mode.

Runs a dork sweep against a TLD (e.g. ".go.id"), collects unique root domains
from the hit URLs, creates child ScanJob records, and dispatches individual
run_scan tasks for each discovered domain.
"""
import asyncio
import logging
from datetime import datetime
from urllib.parse import urlparse

from app.worker import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)

_ALL_MODULES = ["dork_sweep", "page_crawl", "header_probe", "path_probe", "cms_detect", "shodan_probe"]
MAX_CHILD_DOMAINS = 50


def _active_modules() -> list[str]:
    return [m for m in _ALL_MODULES if m != "shodan_probe" or settings.shodan_api_key]


async def _run_tld_sweep_async(scan_id: str, tld: str) -> None:
    from sqlalchemy import select
    from app.core.deps import AsyncSessionLocal
    from app.models.scan import ScanJob, ModuleStatus
    from app.scanner import dork_sweep
    from app.scanner.pipeline import _save_findings
    from app.tasks.scan_tasks import run_scan

    async with AsyncSessionLocal() as db:
        try:
            # Mark parent job as running
            result = await db.execute(select(ScanJob).where(ScanJob.id == scan_id))
            job = result.scalar_one()
            job.status = "running"
            job.updated_at = datetime.utcnow()
            await db.commit()

            # Mark dork_sweep module as running
            ms_result = await db.execute(
                select(ModuleStatus).where(
                    ModuleStatus.scan_job_id == scan_id,
                    ModuleStatus.module == "dork_sweep",
                )
            )
            mod_status = ms_result.scalar_one_or_none()
            if mod_status:
                mod_status.status = "running"
                await db.commit()

            # Run dork sweep against TLD
            sweep_result = await dork_sweep.run(tld)
            raw_findings = sweep_result.get("findings") or []

            # Save dork hits as findings on the parent job
            mapped_findings = [
                {
                    "module": "dork_sweep",
                    "severity": "high",
                    "url": f["url"],
                    "title": f"Google dork hit: {f.get('dork', '')} - {f.get('title', '')}",
                    "description": f.get("snippet", ""),
                    "evidence_text": f.get("snippet", ""),
                    "screenshot_path": None,
                    "screenshot_hash": None,
                    "detected_keywords": [],
                    "injected_links": [],
                }
                for f in raw_findings
                if f.get("url")
            ]
            if mapped_findings:
                await _save_findings(db, scan_id, mapped_findings)

            # Mark dork_sweep module as done/error
            ms_result = await db.execute(
                select(ModuleStatus).where(
                    ModuleStatus.scan_job_id == scan_id,
                    ModuleStatus.module == "dork_sweep",
                )
            )
            mod_status = ms_result.scalar_one_or_none()
            if mod_status:
                mod_status.status = "done" if sweep_result.get("status") == "success" else "error"
                mod_status.error = sweep_result.get("error")
                await db.commit()

            # Collect unique root domains from hit URLs
            seen: set[str] = set()
            unique_domains: list[str] = []
            for f in raw_findings:
                url = f.get("url", "")
                if not url:
                    continue
                netloc = urlparse(url).netloc
                # Strip www. prefix for deduplication
                domain = netloc.removeprefix("www.")
                if domain and domain not in seen:
                    seen.add(domain)
                    unique_domains.append(domain)
                    if len(unique_domains) >= MAX_CHILD_DOMAINS:
                        break

            # Create child ScanJob records and dispatch scan tasks
            for domain in unique_domains:
                child_job = ScanJob(
                    domain=domain,
                    status="pending",
                    scan_type="single",
                    parent_id=scan_id,
                )
                db.add(child_job)
                await db.flush()  # Get child_job.id

                for module in _active_modules():
                    db.add(ModuleStatus(scan_job_id=child_job.id, module=module, status="pending"))

                await db.commit()
                await db.refresh(child_job)

                run_scan.delay(child_job.id, domain)
                logger.info("Dispatched child scan %s for domain %s", child_job.id, domain)

            # Mark parent job as completed
            result = await db.execute(select(ScanJob).where(ScanJob.id == scan_id))
            job = result.scalar_one()
            job.status = "completed"
            job.updated_at = datetime.utcnow()
            await db.commit()

            logger.info(
                "TLD sweep %s completed: %d dork hits, %d child domains dispatched",
                scan_id,
                len(raw_findings),
                len(unique_domains),
            )

        except Exception as e:
            logger.exception("TLD sweep error for scan %s: %s", scan_id, e)
            async with AsyncSessionLocal() as err_db:
                result = await err_db.execute(select(ScanJob).where(ScanJob.id == scan_id))
                job = result.scalar_one_or_none()
                if job:
                    job.status = "error"
                    job.error = str(e)
                    job.updated_at = datetime.utcnow()
                    await err_db.commit()


@celery_app.task(name="tld_sweep_tasks.run_tld_sweep", bind=True, max_retries=0)
def run_tld_sweep(self, scan_id: str, tld: str) -> None:
    asyncio.run(_run_tld_sweep_async(scan_id, tld))

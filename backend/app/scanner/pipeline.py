import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.config import settings
from app.core.deps import AsyncSessionLocal
from app.core.webhook import notify_webhook
from app.models.scan import ScanJob, Finding, ModuleStatus
from app.scanner import dork_sweep, page_crawl, header_probe, path_probe, cms_detect, shodan_probe
from app.scanner import keyword_discovery
from app.scanner.scoring import compute_cvss_lite

logger = logging.getLogger(__name__)


@dataclass
class PipelineModule:
    name: str
    adapter: Callable


async def _adapter_dork_sweep(
    domain: str, scan_id: str, ctx: dict
) -> tuple[dict, list[dict]]:
    result = await dork_sweep.run(domain)
    raw_findings = result.get("findings") or []
    ctx["dork_urls"] = [f["url"] for f in raw_findings if f.get("url")]
    mapped: list[dict] = [
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
    ]
    return result, mapped


async def _adapter_page_crawl(
    domain: str, scan_id: str, ctx: dict
) -> tuple[dict, list[dict]]:
    db: AsyncSession = ctx["db"]
    active_keywords = await keyword_discovery.get_active_keywords(db)
    result = await page_crawl.run(domain, scan_id, ctx.get("dork_urls", []), active_keywords)
    raw_findings = result.get("findings") or []

    # Run keyword discovery on confirmed gambling findings
    for f in raw_findings:
        if f.get("evidence_text"):
            await keyword_discovery.process_finding(
                db=db,
                page_text=f["evidence_text"],
                source_url=f["url"],
                known_keywords=active_keywords,
            )

    return result, raw_findings


async def _adapter_header_probe(
    domain: str, scan_id: str, ctx: dict
) -> tuple[dict, list[dict]]:
    result = await header_probe.run(domain)
    return result, result.get("findings") or []


async def _adapter_path_probe(
    domain: str, scan_id: str, ctx: dict
) -> tuple[dict, list[dict]]:
    result = await path_probe.run(domain)
    return result, result.get("findings") or []


async def _adapter_cms_detect(
    domain: str, scan_id: str, ctx: dict
) -> tuple[dict, list[dict]]:
    result = await cms_detect.run(domain)
    return result, result.get("findings") or []


async def _adapter_shodan_probe(
    domain: str, scan_id: str, ctx: dict
) -> tuple[dict, list[dict]]:
    result = await shodan_probe.run(domain)
    return result, result.get("findings") or []


PIPELINE: list[PipelineModule] = [
    PipelineModule(name="dork_sweep", adapter=_adapter_dork_sweep),
    PipelineModule(name="page_crawl", adapter=_adapter_page_crawl),
    PipelineModule(name="header_probe", adapter=_adapter_header_probe),
    PipelineModule(name="path_probe", adapter=_adapter_path_probe),
    PipelineModule(name="cms_detect", adapter=_adapter_cms_detect),
    PipelineModule(name="shodan_probe", adapter=_adapter_shodan_probe),
]


async def _update_module_status(
    db: AsyncSession,
    scan_id: str,
    module: str,
    status: str,
    error: str | None = None,
) -> None:
    result = await db.execute(
        select(ModuleStatus).where(
            ModuleStatus.scan_job_id == scan_id,
            ModuleStatus.module == module,
        )
    )
    mod_status = result.scalar_one_or_none()
    if mod_status:
        mod_status.status = status
        mod_status.error = error
        await db.commit()


async def _save_findings(
    db: AsyncSession, scan_id: str, raw_findings: list[dict]
) -> None:
    for f in raw_findings:
        keywords = f.get("detected_keywords") or []
        links = f.get("injected_links") or []
        score = compute_cvss_lite(
            severity=f.get("severity", "info"),
            module=f.get("module", "unknown"),
            detected_keywords=keywords,
            injected_links=links,
            has_screenshot=bool(f.get("screenshot_path")),
        )
        finding = Finding(
            scan_job_id=scan_id,
            module=f.get("module", "unknown"),
            severity=f.get("severity", "info"),
            url=f.get("url", ""),
            title=f.get("title", ""),
            description=f.get("description"),
            evidence_text=f.get("evidence_text"),
            screenshot_path=f.get("screenshot_path"),
            screenshot_hash=f.get("screenshot_hash"),
            detected_keywords=json.dumps(keywords),
            injected_links=json.dumps(links),
            cvss_score=score,
        )
        db.add(finding)
    await db.commit()


def _fingerprint(module: str, url: str, title: str) -> tuple:
    # dork_sweep titles contain variable Google snippets — use (module, url) only
    if module == "dork_sweep":
        return (module, url)
    return (module, url, title)


async def _compute_diff(db: AsyncSession, scan_id: str, domain: str) -> None:
    # Find the most recent completed scan for this domain (root scans only)
    prev_result = await db.execute(
        select(ScanJob)
        .where(
            ScanJob.domain == domain,
            ScanJob.status == "completed",
            ScanJob.id != scan_id,
            ScanJob.parent_id.is_(None),
        )
        .order_by(ScanJob.created_at.desc())
        .limit(1)
    )
    prev_job = prev_result.scalar_one_or_none()
    if not prev_job:
        return

    # Build fingerprint set from previous scan
    prev_findings_result = await db.execute(
        select(Finding).where(Finding.scan_job_id == prev_job.id)
    )
    prev_findings = prev_findings_result.scalars().all()
    prev_fps = {_fingerprint(f.module, f.url, f.title) for f in prev_findings}

    # Tag current findings as new or recurring
    curr_findings_result = await db.execute(
        select(Finding).where(Finding.scan_job_id == scan_id)
    )
    curr_findings = curr_findings_result.scalars().all()
    curr_fps: set[tuple] = set()

    new_count = 0
    recurring_count = 0
    for f in curr_findings:
        fp = _fingerprint(f.module, f.url, f.title)
        curr_fps.add(fp)
        if fp in prev_fps:
            f.delta_tag = "recurring"
            recurring_count += 1
        else:
            f.delta_tag = "new"
            new_count += 1

    resolved_count = len(prev_fps - curr_fps)

    # Store diff results on current job
    curr_job_result = await db.execute(select(ScanJob).where(ScanJob.id == scan_id))
    curr_job = curr_job_result.scalar_one()
    curr_job.previous_scan_id = prev_job.id
    curr_job.delta_summary = json.dumps({
        "new": new_count,
        "recurring": recurring_count,
        "resolved": resolved_count,
    })
    await db.commit()


async def run_pipeline(scan_id: str, domain: str) -> None:
    async with AsyncSessionLocal() as db:
        try:
            # Mark job as running
            result = await db.execute(select(ScanJob).where(ScanJob.id == scan_id))
            job = result.scalar_one()
            job.status = "running"
            job.updated_at = datetime.utcnow()
            await db.commit()

            ctx: dict = {"db": db}

            for module in PIPELINE:
                await _update_module_status(db, scan_id, module.name, "running")
                try:
                    raw_result, findings = await module.adapter(domain, scan_id, ctx)
                    if findings:
                        await _save_findings(db, scan_id, findings)
                    await _update_module_status(
                        db,
                        scan_id,
                        module.name,
                        "done" if raw_result.get("status") == "success" else "error",
                        raw_result.get("error"),
                    )
                except Exception as module_err:
                    logger.exception(
                        "Module %s error for scan %s: %s", module.name, scan_id, module_err
                    )
                    await _update_module_status(
                        db, scan_id, module.name, "error", str(module_err)
                    )

            # Compute scan diff against previous scan for same domain
            await _compute_diff(db, scan_id, domain)

            # Notify webhook if critical findings were found
            critical_result = await db.execute(
                select(Finding).where(
                    Finding.scan_job_id == scan_id,
                    Finding.severity == "critical",
                )
            )
            critical_findings = critical_result.scalars().all()
            if critical_findings and settings.webhook_url:
                await notify_webhook(
                    settings.webhook_url,
                    {
                        "event": "critical_finding",
                        "domain": domain,
                        "scan_id": scan_id,
                        "critical_count": len(critical_findings),
                        "findings": [
                            {
                                "title": f.title,
                                "url": f.url,
                                "severity": f.severity,
                                "cvss_score": f.cvss_score,
                                "module": f.module,
                            }
                            for f in critical_findings
                        ],
                    },
                )

            # Mark job as completed
            result = await db.execute(select(ScanJob).where(ScanJob.id == scan_id))
            job = result.scalar_one()
            job.status = "completed"
            job.updated_at = datetime.utcnow()
            await db.commit()

        except Exception as e:
            logger.exception("Pipeline error for scan %s: %s", scan_id, e)
            async with AsyncSessionLocal() as err_db:
                result = await err_db.execute(select(ScanJob).where(ScanJob.id == scan_id))
                job = result.scalar_one_or_none()
                if job:
                    job.status = "error"
                    job.error = str(e)
                    job.updated_at = datetime.utcnow()
                    await err_db.commit()

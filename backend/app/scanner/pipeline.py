import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import AsyncSessionLocal
from app.models.scan import ScanJob, Finding, ModuleStatus
from app.scanner import dork_sweep, page_crawl, header_probe, path_probe, cms_detect
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
            "title": f"Google dork hit: {f.get('dork', '')} — {f.get('title', '')}",
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


PIPELINE: list[PipelineModule] = [
    PipelineModule(name="dork_sweep", adapter=_adapter_dork_sweep),
    PipelineModule(name="page_crawl", adapter=_adapter_page_crawl),
    PipelineModule(name="header_probe", adapter=_adapter_header_probe),
    PipelineModule(name="path_probe", adapter=_adapter_path_probe),
    PipelineModule(name="cms_detect", adapter=_adapter_cms_detect),
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

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db
from app.models.scan import ScanJob, Finding, ModuleStatus
from app.schemas.scan import ScanRequest, ScanResponse, ScanStatusResponse
from app.scanner import dork_sweep, page_crawl, header_probe, path_probe, cms_detect
from app.scanner import keyword_discovery

logger = logging.getLogger(__name__)
router = APIRouter()

MODULES = ["dork_sweep", "page_crawl", "header_probe", "path_probe", "cms_detect"]


async def _update_module_status(
    db: AsyncSession, scan_id: str, module: str, status: str, error: str | None = None
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


async def _save_findings(db: AsyncSession, scan_id: str, raw_findings: list[dict]) -> None:
    for f in raw_findings:
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
            detected_keywords=json.dumps(f.get("detected_keywords") or []),
            injected_links=json.dumps(f.get("injected_links") or []),
        )
        db.add(finding)
    await db.commit()


async def _run_pipeline(scan_id: str, domain: str) -> None:
    from app.core.deps import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            # Mark job as running
            result = await db.execute(select(ScanJob).where(ScanJob.id == scan_id))
            job = result.scalar_one()
            job.status = "running"
            job.updated_at = datetime.utcnow()
            await db.commit()

            # 1. Dork sweep
            await _update_module_status(db, scan_id, "dork_sweep", "running")
            dork_result = await dork_sweep.run(domain)
            dork_findings = dork_result.get("findings") or []
            dork_urls = [f["url"] for f in dork_findings if f.get("url")]
            if dork_findings:
                await _save_findings(db, scan_id, [
                    {
                        "module": "dork_sweep",
                        "severity": "high",
                        "url": f["url"],
                        "title": f"Google dork hit: {f.get('dork', '')} — {f.get('title', '')}",
                        "description": f.get("snippet", ""),
                        "evidence_text": f.get("snippet", ""),
                    }
                    for f in dork_findings
                ])
            await _update_module_status(
                db, scan_id, "dork_sweep",
                "done" if dork_result["status"] == "success" else "error",
                dork_result.get("error"),
            )

            # 2. Page crawl — load active keywords from DB (seed + auto-discovered)
            await _update_module_status(db, scan_id, "page_crawl", "running")
            active_keywords = await keyword_discovery.get_active_keywords(db)
            crawl_result = await page_crawl.run(domain, scan_id, dork_urls, active_keywords)
            if crawl_result.get("findings"):
                await _save_findings(db, scan_id, crawl_result["findings"])

                # Run keyword discovery on every confirmed gambling finding
                for finding in crawl_result["findings"]:
                    if finding.get("evidence_text"):
                        await keyword_discovery.process_finding(
                            db=db,
                            page_text=finding["evidence_text"],
                            source_url=finding["url"],
                            known_keywords=active_keywords,
                        )

            await _update_module_status(
                db, scan_id, "page_crawl",
                "done" if crawl_result["status"] == "success" else "error",
                crawl_result.get("error"),
            )

            # 3. Header probe
            await _update_module_status(db, scan_id, "header_probe", "running")
            header_result = await header_probe.run(domain)
            if header_result.get("findings"):
                await _save_findings(db, scan_id, header_result["findings"])
            await _update_module_status(
                db, scan_id, "header_probe",
                "done" if header_result["status"] == "success" else "error",
                header_result.get("error"),
            )

            # 4. Path probe
            await _update_module_status(db, scan_id, "path_probe", "running")
            path_result = await path_probe.run(domain)
            if path_result.get("findings"):
                await _save_findings(db, scan_id, path_result["findings"])
            await _update_module_status(
                db, scan_id, "path_probe",
                "done" if path_result["status"] == "success" else "error",
                path_result.get("error"),
            )

            # 5. CMS detect
            await _update_module_status(db, scan_id, "cms_detect", "running")
            cms_result = await cms_detect.run(domain)
            if cms_result.get("findings"):
                await _save_findings(db, scan_id, cms_result["findings"])
            await _update_module_status(
                db, scan_id, "cms_detect",
                "done" if cms_result["status"] == "success" else "error",
                cms_result.get("error"),
            )

            # Mark complete
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


@router.post("/scan", response_model=ScanResponse, status_code=202)
async def start_scan(
    body: ScanRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ScanResponse:
    job = ScanJob(domain=body.domain, status="pending")
    db.add(job)
    await db.flush()  # Get ID before commit

    for module in MODULES:
        db.add(ModuleStatus(scan_job_id=job.id, module=module, status="pending"))

    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(_run_pipeline, job.id, body.domain)
    return ScanResponse(scan_id=job.id)


@router.get("/scan/{scan_id}", response_model=ScanStatusResponse)
async def get_scan(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
) -> ScanStatusResponse:
    result = await db.execute(
        select(ScanJob)
        .where(ScanJob.id == scan_id)
        .options(
            selectinload(ScanJob.findings),
            selectinload(ScanJob.module_statuses),
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Deserialize JSON fields on findings
    findings_out = []
    for f in job.findings:
        findings_out.append({
            "id": f.id,
            "scan_job_id": f.scan_job_id,
            "module": f.module,
            "severity": f.severity,
            "url": f.url,
            "title": f.title,
            "description": f.description,
            "evidence_text": f.evidence_text,
            "screenshot_path": f.screenshot_path,
            "screenshot_hash": f.screenshot_hash,
            "detected_keywords": json.loads(f.detected_keywords) if f.detected_keywords else [],
            "injected_links": json.loads(f.injected_links) if f.injected_links else [],
        })

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    findings_out.sort(key=lambda x: severity_order.get(x["severity"], 99))

    return ScanStatusResponse(
        scan_id=job.id,
        domain=job.domain,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        modules=[
            {"module": m.module, "status": m.status, "error": m.error}
            for m in job.module_statuses
        ],
        findings=findings_out,
        error=job.error,
    )

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db
from app.models.scan import ScanJob, Finding, ModuleStatus
from app.schemas.scan import (
    ScanRequest, ScanResponse, ScanStatusResponse, ChildScanSummary,
    ScanHistoryResponse, ScanSummary, FindingCounts,
)
from app.tasks.scan_tasks import run_scan
from app.tasks.tld_sweep_tasks import run_tld_sweep

logger = logging.getLogger(__name__)
router = APIRouter()

MODULES = ["dork_sweep", "page_crawl", "header_probe", "path_probe", "cms_detect"]


@router.post("/scan", response_model=ScanResponse, status_code=202)
async def start_scan(
    body: ScanRequest,
    db: AsyncSession = Depends(get_db),
) -> ScanResponse:
    is_sweep = body.domain.startswith(".")

    if is_sweep:
        job = ScanJob(domain=body.domain, status="pending", scan_type="tld_sweep")
        db.add(job)
        await db.flush()  # Get ID before commit

        # TLD sweep only gets a single module status for dork_sweep;
        # child jobs will have their own full module statuses
        db.add(ModuleStatus(scan_job_id=job.id, module="dork_sweep", status="pending"))

        await db.commit()
        await db.refresh(job)

        run_tld_sweep.delay(job.id, body.domain)
    else:
        job = ScanJob(domain=body.domain, status="pending", scan_type="single")
        db.add(job)
        await db.flush()  # Get ID before commit

        for module in MODULES:
            db.add(ModuleStatus(scan_job_id=job.id, module=module, status="pending"))

        await db.commit()
        await db.refresh(job)

        run_scan.delay(job.id, body.domain)

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
            selectinload(ScanJob.children).selectinload(ScanJob.findings),
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
            "cvss_score": f.cvss_score,
        })

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    findings_out.sort(key=lambda x: severity_order.get(x["severity"], 99))

    # Build children summary list
    children_out = [
        ChildScanSummary(
            scan_id=c.id,
            domain=c.domain,
            status=c.status,
            finding_count=len(c.findings),
        )
        for c in job.children
    ]

    return ScanStatusResponse(
        scan_id=job.id,
        domain=job.domain,
        status=job.status,
        scan_type=job.scan_type,
        created_at=job.created_at,
        updated_at=job.updated_at,
        modules=[
            {"module": m.module, "status": m.status, "error": m.error}
            for m in job.module_statuses
        ],
        findings=findings_out,
        children=children_out,
        error=job.error,
    )


@router.get("/scans", response_model=ScanHistoryResponse)
async def list_scans(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
    domain: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> ScanHistoryResponse:
    # Base query: root scans only (no children)
    base = select(ScanJob).where(ScanJob.parent_id.is_(None))
    if status:
        base = base.where(ScanJob.status == status)
    if domain:
        base = base.where(ScanJob.domain.ilike(f"%{domain}%"))

    # Total count
    count_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = count_result.scalar_one()

    # Paginated scan jobs
    jobs_result = await db.execute(
        base.order_by(ScanJob.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    jobs = jobs_result.scalars().all()

    if not jobs:
        return ScanHistoryResponse(total=total, page=page, limit=limit, scans=[])

    job_ids = [j.id for j in jobs]

    # Aggregate finding counts per scan_id in one query
    counts_result = await db.execute(
        select(
            Finding.scan_job_id,
            func.count().label("total"),
            func.sum(case((Finding.severity == "critical", 1), else_=0)).label("critical"),
            func.sum(case((Finding.severity == "high", 1), else_=0)).label("high"),
            func.sum(case((Finding.severity == "medium", 1), else_=0)).label("medium"),
            func.sum(case((Finding.severity == "low", 1), else_=0)).label("low"),
        )
        .where(Finding.scan_job_id.in_(job_ids))
        .group_by(Finding.scan_job_id)
    )
    counts_by_id: dict[str, dict] = {
        row.scan_job_id: {
            "total": row.total,
            "critical": row.critical,
            "high": row.high,
            "medium": row.medium,
            "low": row.low,
        }
        for row in counts_result
    }

    scans = [
        ScanSummary(
            scan_id=j.id,
            domain=j.domain,
            status=j.status,
            scan_type=j.scan_type,
            created_at=j.created_at,
            updated_at=j.updated_at,
            finding_counts=FindingCounts(**counts_by_id.get(j.id, {})),
        )
        for j in jobs
    ]
    return ScanHistoryResponse(total=total, page=page, limit=limit, scans=scans)

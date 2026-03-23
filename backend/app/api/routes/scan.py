import csv
import io
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db, redis_client
from app.core.config import settings
from app.core.limiter import limiter
from app.models.scan import ScanJob, Finding, ModuleStatus
from app.schemas.scan import (
    ScanRequest, ScanResponse, ScanStatusResponse, ChildScanSummary,
    ScanHistoryResponse, ScanSummary, FindingCounts,
    TrendPoint, TrendResponse, BulkScanItem, BulkScanResponse,
)
from app.schemas.finding import LifecycleStatus
from app.tasks.scan_tasks import run_scan
from app.tasks.tld_sweep_tasks import run_tld_sweep


class LifecyclePatch(BaseModel):
    lifecycle_status: LifecycleStatus

logger = logging.getLogger(__name__)
router = APIRouter()

MODULES = ["dork_sweep", "page_crawl", "header_probe", "path_probe", "cms_detect", "shodan_probe"]
TERMINAL_STATUSES = {"completed", "error", "cancelled"}
SCAN_CACHE_TTL = 300  # seconds


@router.post("/scan", response_model=ScanResponse, status_code=202)
@limiter.limit("10/minute")
async def start_scan(
    request: Request,
    body: ScanRequest,
    db: AsyncSession = Depends(get_db),
) -> ScanResponse:
    is_sweep = body.domain.startswith(".")
    active_modules = [m for m in MODULES if m != "shodan_probe" or settings.shodan_api_key]

    if is_sweep:
        job = ScanJob(domain=body.domain, status="pending", scan_type="tld_sweep")
        db.add(job)
        await db.flush()

        db.add(ModuleStatus(scan_job_id=job.id, module="dork_sweep", status="pending"))

        await db.commit()
        await db.refresh(job)

        task = run_tld_sweep.delay(job.id, body.domain)
        job.celery_task_id = task.id
        await db.commit()
    else:
        job = ScanJob(domain=body.domain, status="pending", scan_type="single")
        db.add(job)
        await db.flush()

        for module in active_modules:
            db.add(ModuleStatus(scan_job_id=job.id, module=module, status="pending"))

        await db.commit()
        await db.refresh(job)

        task = run_scan.delay(job.id, body.domain)
        job.celery_task_id = task.id
        await db.commit()

    return ScanResponse(scan_id=job.id)


@router.delete("/scan/{scan_id}", status_code=200)
async def cancel_scan(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(ScanJob).where(ScanJob.id == scan_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Scan not found")
    if job.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel scan with status '{job.status}'")

    if job.celery_task_id:
        from app.worker import celery_app
        celery_app.control.revoke(job.celery_task_id, terminate=True)

    job.status = "cancelled"
    job.updated_at = datetime.utcnow()
    await db.commit()
    return {"scan_id": scan_id, "status": "cancelled"}


@router.get("/scan/{scan_id}", response_model=ScanStatusResponse)
async def get_scan(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
) -> ScanStatusResponse:
    # Serve from cache for terminal scans (immutable once done)
    cache_key = f"scan:{scan_id}"
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return ScanStatusResponse.model_validate_json(cached)
    except Exception:
        pass  # Redis unavailable - fall through to DB

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
            "lifecycle_status": f.lifecycle_status,
            "delta_tag": f.delta_tag,
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

    delta_summary = json.loads(job.delta_summary) if job.delta_summary else None

    response = ScanStatusResponse(
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
        previous_scan_id=job.previous_scan_id,
        delta_summary=delta_summary,
    )

    # Cache terminal scans - they are immutable once done
    if job.status in TERMINAL_STATUSES:
        try:
            await redis_client.setex(cache_key, SCAN_CACHE_TTL, response.model_dump_json())
        except Exception:
            pass  # Redis unavailable - non-fatal

    return response


@router.patch("/finding/{finding_id}/lifecycle")
async def patch_finding_lifecycle(
    finding_id: str,
    body: LifecyclePatch,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Finding).where(Finding.id == finding_id))
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    finding.lifecycle_status = body.lifecycle_status.value
    await db.commit()

    # Invalidate Redis cache for the parent scan — lifecycle status changed
    try:
        await redis_client.delete(f"scan:{finding.scan_job_id}")
    except Exception:
        pass

    return {"id": finding_id, "lifecycle_status": finding.lifecycle_status}


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


@router.get("/trend", response_model=TrendResponse)
async def get_trend(
    domain: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> TrendResponse:
    jobs_result = await db.execute(
        select(ScanJob)
        .where(
            ScanJob.domain == domain,
            ScanJob.parent_id.is_(None),
            ScanJob.status.in_(["completed", "error"]),
        )
        .order_by(ScanJob.created_at.asc())
    )
    jobs = jobs_result.scalars().all()

    if not jobs:
        return TrendResponse(domain=domain, points=[])

    job_ids = [j.id for j in jobs]

    counts_result = await db.execute(
        select(
            Finding.scan_job_id,
            func.count().label("total"),
            func.sum(case((Finding.severity == "critical", 1), else_=0)).label("critical"),
            func.sum(case((Finding.severity == "high", 1), else_=0)).label("high"),
            func.sum(case((Finding.severity == "medium", 1), else_=0)).label("medium"),
            func.sum(case((Finding.severity == "low", 1), else_=0)).label("low"),
            func.max(Finding.cvss_score).label("cvss_max"),
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
            "cvss_max": row.cvss_max,
        }
        for row in counts_result
    }

    points = [
        TrendPoint(
            scan_id=j.id,
            created_at=j.created_at,
            status=j.status,
            finding_counts=FindingCounts(**{
                k: v for k, v in counts_by_id.get(j.id, {}).items()
                if k != "cvss_max"
            }),
            cvss_max=counts_by_id.get(j.id, {}).get("cvss_max"),
        )
        for j in jobs
    ]

    return TrendResponse(domain=domain, points=points)


@router.post("/scan/bulk", response_model=BulkScanResponse, status_code=202)
@limiter.limit("3/minute")
async def bulk_scan(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> BulkScanResponse:
    content = await file.read()
    text = content.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))

    seen: set[str] = set()
    domains: list[str] = []
    for row in reader:
        if not row:
            continue
        raw = row[0].strip()
        if not raw or raw.lower() == "domain":  # skip header
            continue
        # Normalize same as ScanRequest
        for prefix in ("https://", "http://"):
            if raw.startswith(prefix):
                raw = raw[len(prefix):]
        raw = raw.rstrip("/").lower()
        if raw and raw not in seen:
            seen.add(raw)
            domains.append(raw)

    scans: list[BulkScanItem] = []
    for domain in domains:
        is_sweep = domain.startswith(".")
        if is_sweep:
            job = ScanJob(domain=domain, status="pending", scan_type="tld_sweep")
            db.add(job)
            await db.flush()
            db.add(ModuleStatus(scan_job_id=job.id, module="dork_sweep", status="pending"))
            await db.commit()
            await db.refresh(job)
            run_tld_sweep.delay(job.id, domain)
        else:
            job = ScanJob(domain=domain, status="pending", scan_type="single")
            db.add(job)
            await db.flush()
            for module in MODULES:
                db.add(ModuleStatus(scan_job_id=job.id, module=module, status="pending"))
            await db.commit()
            await db.refresh(job)
            run_scan.delay(job.id, domain)
        scans.append(BulkScanItem(domain=domain, scan_id=job.id))

    return BulkScanResponse(count=len(scans), scans=scans)

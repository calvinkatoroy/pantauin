"""
GET /api/dashboard - executive aggregate view across all scans.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, case, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.scan import ScanJob, Finding

router = APIRouter()


class DomainStats(BaseModel):
    domain: str
    critical: int
    high: int
    total: int


class RecentCritical(BaseModel):
    finding_id: str
    title: str
    url: str
    domain: str
    scan_id: str
    cvss_score: float | None
    created_at: datetime


class SeverityBreakdown(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class DashboardResponse(BaseModel):
    total_scans: int
    total_findings: int
    domains_scanned: int
    scans_last_30_days: int
    findings_last_30_days: int
    finding_by_severity: SeverityBreakdown
    open_by_severity: SeverityBreakdown
    top_affected_domains: list[DomainStats]
    recent_critical: list[RecentCritical]


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(db: AsyncSession = Depends(get_db)) -> DashboardResponse:
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # Total scans (root only)
    total_scans_r = await db.execute(
        select(func.count()).where(ScanJob.parent_id.is_(None))
    )
    total_scans = total_scans_r.scalar_one()

    # Unique domains scanned
    domains_r = await db.execute(
        select(func.count(distinct(ScanJob.domain))).where(ScanJob.parent_id.is_(None))
    )
    domains_scanned = domains_r.scalar_one()

    # Scans last 30 days
    recent_scans_r = await db.execute(
        select(func.count()).where(
            ScanJob.parent_id.is_(None),
            ScanJob.created_at >= thirty_days_ago,
        )
    )
    scans_last_30_days = recent_scans_r.scalar_one()

    # Total findings + breakdown by severity
    sev_r = await db.execute(
        select(
            func.count().label("total"),
            func.sum(case((Finding.severity == "critical", 1), else_=0)).label("critical"),
            func.sum(case((Finding.severity == "high", 1), else_=0)).label("high"),
            func.sum(case((Finding.severity == "medium", 1), else_=0)).label("medium"),
            func.sum(case((Finding.severity == "low", 1), else_=0)).label("low"),
            func.sum(case((Finding.severity == "info", 1), else_=0)).label("info"),
        )
    )
    sev_row = sev_r.one()
    total_findings = sev_row.total or 0
    finding_by_severity = SeverityBreakdown(
        critical=sev_row.critical or 0,
        high=sev_row.high or 0,
        medium=sev_row.medium or 0,
        low=sev_row.low or 0,
        info=sev_row.info or 0,
    )

    # Findings last 30 days
    recent_findings_r = await db.execute(
        select(func.count()).where(Finding.created_at >= thirty_days_ago)
    )
    findings_last_30_days = recent_findings_r.scalar_one()

    # Open findings by severity (lifecycle_status = open)
    open_r = await db.execute(
        select(
            func.sum(case((Finding.severity == "critical", 1), else_=0)).label("critical"),
            func.sum(case((Finding.severity == "high", 1), else_=0)).label("high"),
            func.sum(case((Finding.severity == "medium", 1), else_=0)).label("medium"),
            func.sum(case((Finding.severity == "low", 1), else_=0)).label("low"),
        ).where(Finding.lifecycle_status == "open")
    )
    open_row = open_r.one()
    open_by_severity = SeverityBreakdown(
        critical=open_row.critical or 0,
        high=open_row.high or 0,
        medium=open_row.medium or 0,
        low=open_row.low or 0,
    )

    # Top 10 domains by critical+high finding count
    top_r = await db.execute(
        select(
            ScanJob.domain,
            func.sum(case((Finding.severity == "critical", 1), else_=0)).label("critical"),
            func.sum(case((Finding.severity == "high", 1), else_=0)).label("high"),
            func.count(Finding.id).label("total"),
        )
        .join(Finding, Finding.scan_job_id == ScanJob.id)
        .where(ScanJob.parent_id.is_(None))
        .group_by(ScanJob.domain)
        .order_by((
            func.sum(case((Finding.severity == "critical", 1), else_=0)) +
            func.sum(case((Finding.severity == "high", 1), else_=0))
        ).desc())
        .limit(10)
    )
    top_affected_domains = [
        DomainStats(domain=row.domain, critical=row.critical or 0,
                    high=row.high or 0, total=row.total or 0)
        for row in top_r
    ]

    # Last 5 critical findings
    crit_r = await db.execute(
        select(Finding, ScanJob.domain)
        .join(ScanJob, ScanJob.id == Finding.scan_job_id)
        .where(Finding.severity == "critical")
        .order_by(Finding.created_at.desc())
        .limit(5)
    )
    recent_critical = [
        RecentCritical(
            finding_id=row.Finding.id,
            title=row.Finding.title,
            url=row.Finding.url,
            domain=row.domain,
            scan_id=row.Finding.scan_job_id,
            cvss_score=row.Finding.cvss_score,
            created_at=row.Finding.created_at,
        )
        for row in crit_r
    ]

    return DashboardResponse(
        total_scans=total_scans,
        total_findings=total_findings,
        domains_scanned=domains_scanned,
        scans_last_30_days=scans_last_30_days,
        findings_last_30_days=findings_last_30_days,
        finding_by_severity=finding_by_severity,
        open_by_severity=open_by_severity,
        top_affected_domains=top_affected_domains,
        recent_critical=recent_critical,
    )

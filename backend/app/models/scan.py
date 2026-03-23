import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Float, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.deps import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ScanJob(Base):
    __tablename__ = "scan_jobs"
    __table_args__ = (
        Index("ix_scan_jobs_domain", "domain"),
        Index("ix_scan_jobs_status", "status"),
        Index("ix_scan_jobs_parent_id", "parent_id"),
        Index("ix_scan_jobs_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|completed|error
    scan_type: Mapped[str] = mapped_column(String(20), default="single")  # single|tld_sweep
    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("scan_jobs.id"), nullable=True)
    previous_scan_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # diff baseline (no FK, informational)
    delta_summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: {"new": N, "recurring": N, "resolved": N}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    findings: Mapped[list["Finding"]] = relationship("Finding", back_populates="scan_job", cascade="all, delete-orphan")
    module_statuses: Mapped[list["ModuleStatus"]] = relationship("ModuleStatus", back_populates="scan_job", cascade="all, delete-orphan")
    children: Mapped[list["ScanJob"]] = relationship("ScanJob", foreign_keys=[parent_id], back_populates="parent")
    parent: Mapped["ScanJob | None"] = relationship("ScanJob", foreign_keys=[parent_id], back_populates="children", remote_side="ScanJob.id")


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        Index("ix_findings_scan_job_id", "scan_job_id"),
        Index("ix_findings_severity", "severity"),
        Index("ix_findings_lifecycle_status", "lifecycle_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scan_job_id: Mapped[str] = mapped_column(String(36), ForeignKey("scan_jobs.id"), nullable=False)
    module: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # critical|high|medium|low|info
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detected_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array as text
    injected_links: Mapped[str | None] = mapped_column(Text, nullable=True)    # JSON array as text
    cvss_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(String(30), default="open", nullable=False)  # open|in-remediation|resolved|accepted-risk
    delta_tag: Mapped[str | None] = mapped_column(String(20), nullable=True)  # new|recurring
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scan_job: Mapped["ScanJob"] = relationship("ScanJob", back_populates="findings")


class ModuleStatus(Base):
    __tablename__ = "module_statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_job_id: Mapped[str] = mapped_column(String(36), ForeignKey("scan_jobs.id"), nullable=False)
    module: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|done|error
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    scan_job: Mapped["ScanJob"] = relationship("ScanJob", back_populates="module_statuses")


class ScanSchedule(Base):
    __tablename__ = "scan_schedules"
    __table_args__ = (
        Index("ix_scan_schedules_domain", "domain"),
        Index("ix_scan_schedules_next_run_at", "next_run_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    interval: Mapped[str] = mapped_column(String(20), nullable=False)  # daily|weekly|monthly
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DiscoveredKeyword(Base):
    __tablename__ = "discovered_keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    frequency: Mapped[int] = mapped_column(Integer, default=1)       # how many sites it was found on
    confidence: Mapped[float] = mapped_column(Float, default=0.0)    # 0.0 – 1.0
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected
    source_urls: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array of source URLs
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False)    # True = original keywords.py seed terms

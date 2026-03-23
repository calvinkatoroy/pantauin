import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.deps import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|completed|error
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    findings: Mapped[list["Finding"]] = relationship("Finding", back_populates="scan_job", cascade="all, delete-orphan")
    module_statuses: Mapped[list["ModuleStatus"]] = relationship("ModuleStatus", back_populates="scan_job", cascade="all, delete-orphan")


class Finding(Base):
    __tablename__ = "findings"

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

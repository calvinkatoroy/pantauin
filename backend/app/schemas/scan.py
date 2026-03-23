from datetime import datetime
from pydantic import BaseModel, field_validator
from app.schemas.finding import FindingSchema


class ScanRequest(BaseModel):
    domain: str

    @field_validator("domain")
    @classmethod
    def clean_domain(cls, v: str) -> str:
        v = v.strip().lower()
        # Strip protocol if provided
        for prefix in ("https://", "http://"):
            if v.startswith(prefix):
                v = v[len(prefix):]
        # Strip trailing slash
        v = v.rstrip("/")
        return v


class ModuleStatusSchema(BaseModel):
    module: str
    status: str  # pending|running|done|error
    error: str | None = None

    model_config = {"from_attributes": True}


class ChildScanSummary(BaseModel):
    scan_id: str
    domain: str
    status: str
    finding_count: int

    model_config = {"from_attributes": True}


class ScanResponse(BaseModel):
    scan_id: str


class FindingCounts(BaseModel):
    total: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class ScanSummary(BaseModel):
    scan_id: str
    domain: str
    status: str
    scan_type: str
    created_at: datetime
    updated_at: datetime
    finding_counts: FindingCounts


class ScanHistoryResponse(BaseModel):
    total: int
    page: int
    limit: int
    scans: list[ScanSummary]


class TrendPoint(BaseModel):
    scan_id: str
    created_at: datetime
    status: str
    finding_counts: FindingCounts
    cvss_max: float | None = None


class TrendResponse(BaseModel):
    domain: str
    points: list[TrendPoint]


class BulkScanItem(BaseModel):
    domain: str
    scan_id: str


class BulkScanResponse(BaseModel):
    count: int
    scans: list[BulkScanItem]


class ScanStatusResponse(BaseModel):
    scan_id: str
    domain: str
    status: str
    scan_type: str = "single"
    created_at: datetime
    updated_at: datetime
    modules: list[ModuleStatusSchema]
    findings: list[FindingSchema]
    children: list[ChildScanSummary] = []
    error: str | None = None
    previous_scan_id: str | None = None
    delta_summary: dict | None = None  # {"new": N, "recurring": N, "resolved": N}

    model_config = {"from_attributes": True}

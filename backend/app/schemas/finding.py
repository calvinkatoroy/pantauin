from enum import Enum
from pydantic import BaseModel


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class LifecycleStatus(str, Enum):
    open = "open"
    in_remediation = "in-remediation"
    resolved = "resolved"
    accepted_risk = "accepted-risk"


class FindingSchema(BaseModel):
    id: str
    scan_job_id: str
    module: str
    severity: Severity
    url: str
    title: str
    description: str | None = None
    evidence_text: str | None = None
    screenshot_path: str | None = None
    screenshot_hash: str | None = None
    detected_keywords: list[str] | None = None
    injected_links: list[str] | None = None
    cvss_score: float | None = None
    lifecycle_status: str = "open"
    delta_tag: str | None = None  # new|recurring

    model_config = {"from_attributes": True}

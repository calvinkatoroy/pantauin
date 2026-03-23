from enum import Enum
from pydantic import BaseModel


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


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

    model_config = {"from_attributes": True}

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


class ScanResponse(BaseModel):
    scan_id: str


class ScanStatusResponse(BaseModel):
    scan_id: str
    domain: str
    status: str
    created_at: datetime
    updated_at: datetime
    modules: list[ModuleStatusSchema]
    findings: list[FindingSchema]
    error: str | None = None

    model_config = {"from_attributes": True}

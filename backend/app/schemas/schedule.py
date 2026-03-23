from datetime import datetime
from pydantic import BaseModel, field_validator


class ScheduleRequest(BaseModel):
    domain: str
    interval: str  # daily|weekly|monthly

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, v: str) -> str:
        if v not in ("daily", "weekly", "monthly"):
            raise ValueError("interval must be daily, weekly, or monthly")
        return v

    @field_validator("domain")
    @classmethod
    def clean_domain(cls, v: str) -> str:
        v = v.strip().lower()
        for prefix in ("https://", "http://"):
            if v.startswith(prefix):
                v = v[len(prefix):]
        return v.rstrip("/")


class SchedulePatch(BaseModel):
    enabled: bool | None = None
    interval: str | None = None

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, v: str | None) -> str | None:
        if v is not None and v not in ("daily", "weekly", "monthly"):
            raise ValueError("interval must be daily, weekly, or monthly")
        return v


class ScheduleResponse(BaseModel):
    id: str
    domain: str
    interval: str
    enabled: bool
    created_at: datetime
    last_run_at: datetime | None = None
    next_run_at: datetime

    model_config = {"from_attributes": True}


class ScheduleListResponse(BaseModel):
    total: int
    schedules: list[ScheduleResponse]

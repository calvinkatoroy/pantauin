import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.scan import ScanSchedule
from app.schemas.schedule import (
    ScheduleRequest, SchedulePatch, ScheduleResponse, ScheduleListResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_INTERVAL_DELTA: dict[str, timedelta] = {
    "daily":   timedelta(days=1),
    "weekly":  timedelta(weeks=1),
    "monthly": timedelta(days=30),
}


def _next_run(interval: str, from_dt: datetime) -> datetime:
    return from_dt + _INTERVAL_DELTA[interval]


@router.post("/schedules", response_model=ScheduleResponse, status_code=201)
async def create_schedule(
    body: ScheduleRequest,
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    now = datetime.utcnow()
    schedule = ScanSchedule(
        domain=body.domain,
        interval=body.interval,
        enabled=True,
        next_run_at=_next_run(body.interval, now),
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return ScheduleResponse.model_validate(schedule)


@router.get("/schedules", response_model=ScheduleListResponse)
async def list_schedules(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> ScheduleListResponse:
    count_result = await db.execute(select(func.count()).select_from(ScanSchedule))
    total = count_result.scalar_one()

    result = await db.execute(
        select(ScanSchedule)
        .order_by(ScanSchedule.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    schedules = result.scalars().all()
    return ScheduleListResponse(
        total=total,
        schedules=[ScheduleResponse.model_validate(s) for s in schedules],
    )


@router.patch("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: str,
    body: SchedulePatch,
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    result = await db.execute(select(ScanSchedule).where(ScanSchedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if body.enabled is not None:
        schedule.enabled = body.enabled
    if body.interval is not None:
        schedule.interval = body.interval
        schedule.next_run_at = _next_run(body.interval, datetime.utcnow())

    await db.commit()
    await db.refresh(schedule)
    return ScheduleResponse.model_validate(schedule)


@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(ScanSchedule).where(ScanSchedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await db.delete(schedule)
    await db.commit()

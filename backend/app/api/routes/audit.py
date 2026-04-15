import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_role, CurrentUser
from app.core.deps import get_db
from app.models.scan import AuditLog

router = APIRouter()


class AuditEntry(BaseModel):
    id: int
    action: str
    actor: str
    ip_address: str | None
    resource_type: str | None
    resource_id: str | None
    extra: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditListResponse(BaseModel):
    total: int
    page: int
    limit: int
    entries: list[AuditEntry]


@router.get("/audit", response_model=AuditListResponse)
async def list_audit(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    action: str | None = None,
    actor: str | None = None,
    _: CurrentUser = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> AuditListResponse:
    base = select(AuditLog)
    if action:
        base = base.where(AuditLog.action == action)
    if actor:
        base = base.where(AuditLog.actor.ilike(f"%{actor}%"))

    count_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = count_result.scalar_one()

    result = await db.execute(
        base.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = result.scalars().all()

    entries = [
        AuditEntry(
            id=r.id,
            action=r.action,
            actor=r.actor,
            ip_address=r.ip_address,
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            extra=json.loads(r.extra) if r.extra else None,
            created_at=r.created_at,
        )
        for r in rows
    ]

    return AuditListResponse(total=total, page=page, limit=limit, entries=entries)

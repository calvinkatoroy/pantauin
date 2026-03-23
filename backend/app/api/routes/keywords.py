from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.scan import DiscoveredKeyword

router = APIRouter()


class KeywordOut(BaseModel):
    id: int
    keyword: str
    frequency: int
    confidence: float
    status: str
    is_seed: bool
    first_seen_at: datetime
    approved_at: datetime | None = None
    source_count: int = 0

    model_config = {"from_attributes": True}


class KeywordStats(BaseModel):
    total: int
    approved: int
    pending: int
    rejected: int
    seed: int
    auto_discovered: int


@router.get("/keywords", response_model=list[KeywordOut])
async def list_keywords(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[KeywordOut]:
    query = select(DiscoveredKeyword).order_by(
        DiscoveredKeyword.frequency.desc(),
        DiscoveredKeyword.first_seen_at.desc(),
    )
    if status:
        query = query.where(DiscoveredKeyword.status == status)

    result = await db.execute(query)
    keywords = result.scalars().all()

    out = []
    for kw in keywords:
        import json
        sources = json.loads(kw.source_urls or "[]")
        out.append(KeywordOut(
            id=kw.id,
            keyword=kw.keyword,
            frequency=kw.frequency,
            confidence=kw.confidence,
            status=kw.status,
            is_seed=kw.is_seed,
            first_seen_at=kw.first_seen_at,
            approved_at=kw.approved_at,
            source_count=len(sources),
        ))
    return out


@router.get("/keywords/stats", response_model=KeywordStats)
async def keyword_stats(db: AsyncSession = Depends(get_db)) -> KeywordStats:
    result = await db.execute(select(DiscoveredKeyword))
    all_kw = result.scalars().all()

    return KeywordStats(
        total=len(all_kw),
        approved=sum(1 for k in all_kw if k.status == "approved"),
        pending=sum(1 for k in all_kw if k.status == "pending"),
        rejected=sum(1 for k in all_kw if k.status == "rejected"),
        seed=sum(1 for k in all_kw if k.is_seed),
        auto_discovered=sum(1 for k in all_kw if not k.is_seed and k.status == "approved"),
    )


@router.patch("/keywords/{keyword_id}/approve", response_model=KeywordOut)
async def approve_keyword(
    keyword_id: int,
    db: AsyncSession = Depends(get_db),
) -> KeywordOut:
    result = await db.execute(
        select(DiscoveredKeyword).where(DiscoveredKeyword.id == keyword_id)
    )
    kw = result.scalar_one_or_none()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")

    kw.status = "approved"
    kw.approved_at = datetime.utcnow()
    await db.commit()
    await db.refresh(kw)

    import json
    return KeywordOut(
        id=kw.id, keyword=kw.keyword, frequency=kw.frequency,
        confidence=kw.confidence, status=kw.status, is_seed=kw.is_seed,
        first_seen_at=kw.first_seen_at, approved_at=kw.approved_at,
        source_count=len(json.loads(kw.source_urls or "[]")),
    )


@router.patch("/keywords/{keyword_id}/reject", response_model=KeywordOut)
async def reject_keyword(
    keyword_id: int,
    db: AsyncSession = Depends(get_db),
) -> KeywordOut:
    result = await db.execute(
        select(DiscoveredKeyword).where(DiscoveredKeyword.id == keyword_id)
    )
    kw = result.scalar_one_or_none()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")

    kw.status = "rejected"
    await db.commit()
    await db.refresh(kw)

    import json
    return KeywordOut(
        id=kw.id, keyword=kw.keyword, frequency=kw.frequency,
        confidence=kw.confidence, status=kw.status, is_seed=kw.is_seed,
        first_seen_at=kw.first_seen_at, approved_at=kw.approved_at,
        source_count=len(json.loads(kw.source_urls or "[]")),
    )

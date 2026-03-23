from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        from app.models import scan as _  # noqa: F401 — import models to register with Base
        await conn.run_sync(Base.metadata.create_all)

    # Seed static keyword list into discovered_keywords table on first run
    from app.scanner.keyword_discovery import seed_keywords
    async with AsyncSessionLocal() as session:
        await seed_keywords(session)

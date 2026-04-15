"""
Shared pytest fixtures.

Sets up an in-memory SQLite database for every test, overrides the FastAPI
get_db dependency, and mocks Redis and Celery so tests run without external
infrastructure.
"""
import os

# Set env vars BEFORE any app modules are imported so that module-level
# objects (engine, settings) are created with test values.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["API_KEY"] = ""          # auth disabled - no users in DB
os.environ["REDIS_URL"] = "redis://localhost:6379/0"  # mocked below

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Single shared in-memory engine for the entire test session.
# StaticPool ensures all connections share the same SQLite in-memory DB.
TEST_ENGINE = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
TestSession = async_sessionmaker(TEST_ENGINE, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    """Drop and recreate all tables before each test for isolation."""
    import app.models.scan  # noqa - registers models with Base metadata
    from app.core.deps import Base
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client():
    """
    httpx AsyncClient wired to the FastAPI app with:
      - DB overridden to the test in-memory SQLite
      - Redis mocked (get returns None, set/delete are no-ops)
      - Celery tasks mocked so no worker is needed
    """
    from app.main import app
    from app.core import deps as _deps
    from app.core.deps import get_db

    # Override AsyncSessionLocal used by log_action and other direct callers.
    # audit.py imports AsyncSessionLocal at module load time, so we must patch
    # the name in that module directly, not just in deps.
    _deps.AsyncSessionLocal = TestSession
    import app.core.audit as _audit
    _audit.AsyncSessionLocal = TestSession

    # Mock Redis to prevent connection errors
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = True
    _deps.redis_client = mock_redis

    # Also patch redis_client as imported directly in scan route module
    import app.api.routes.scan as _scan_route
    _scan_route.redis_client = mock_redis

    async def _override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    # Disable rate limiting so tests can make many requests from the same IP
    from app.core.limiter import limiter as _limiter
    _limiter.enabled = False

    with (
        patch("app.tasks.scan_tasks.run_scan.delay", return_value=MagicMock(id="mock-task-id")),
        patch("app.tasks.tld_sweep_tasks.run_tld_sweep.delay", return_value=MagicMock(id="mock-task-id")),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac

    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

async def create_admin(client: AsyncClient) -> dict:
    """Set up the first admin account and return {api_key, username, role}."""
    resp = await client.post(
        "/api/auth/setup",
        json={"username": "admin", "password": "adminpass123"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def create_analyst(client: AsyncClient, admin_key: str) -> dict:
    """Create an analyst user via admin API, return UserOut dict."""
    resp = await client.post(
        "/api/auth/users",
        json={"username": "analyst1", "password": "analystpass1", "role": "analyst"},
        headers={"X-API-Key": admin_key},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()

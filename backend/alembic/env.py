import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Alembic Config object
config = context.config

# Set up loggers from ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import models so their metadata is registered
from app.core.deps import Base  # noqa: E402
import app.models.scan  # noqa: E402, F401

target_metadata = Base.metadata

# Override sqlalchemy.url from DATABASE_URL env var if set
_db_url = os.environ.get("DATABASE_URL", "")
if _db_url:
    # asyncpg driver is async-only; Alembic needs the sync psycopg2 equivalent
    # for offline/online sync mode. Map async drivers to sync equivalents.
    _sync_url = (
        _db_url
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("sqlite+aiosqlite://", "sqlite://")
    )
    config.set_main_option("sqlalchemy.url", _sync_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection needed)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using async engine (maps to sync connection internally)."""
    # Use async engine but run migrations via run_sync
    from sqlalchemy.ext.asyncio import create_async_engine

    _db_url = os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url", ""))
    # Alembic's run_sync needs the raw sync driver, not asyncpg
    _sync_url = (
        _db_url
        .replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        .replace("sqlite+aiosqlite://", "sqlite://")
    )

    from sqlalchemy import create_engine
    connectable = create_engine(_sync_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        do_run_migrations(connection)

    connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

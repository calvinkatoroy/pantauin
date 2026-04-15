"""
Authentication and role-based access control.

Two modes, selected at runtime:

  Legacy mode (no users in DB):
    X-API-Key must match settings.api_key (or auth is disabled when that is empty).
    A synthetic admin CurrentUser is returned so role checks pass.

  Multi-user mode (users exist in DB):
    X-API-Key must match a User.api_key for an active user.
    Role (admin | analyst | read-only) is read from the User row.

Switching modes:
    Create the first admin via POST /api/auth/setup (only works when no users exist).
    After that, legacy mode is automatically replaced by multi-user mode.

Role matrix:
    admin      - all operations including user management
    analyst    - start/cancel scans, lifecycle patches, reports, schedules, audit log
    read-only  - GET endpoints only (dashboard, history, scan status)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Sequence

import bcrypt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass
class CurrentUser:
    id: str
    username: str
    role: str  # admin | analyst | read-only
    api_key: str = field(repr=False)


# Synthetic user returned in legacy mode
_LEGACY_ADMIN = CurrentUser(id="legacy", username="legacy", role="admin", api_key="")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def generate_api_key() -> str:
    return uuid.uuid4().hex  # 32-char hex, no dashes


async def _users_exist(db: AsyncSession) -> bool:
    from app.models.scan import User
    result = await db.execute(select(User).limit(1))
    return result.scalar_one_or_none() is not None


async def get_current_user(
    key: str | None = Security(_api_key_header),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """
    FastAPI dependency: returns CurrentUser for the request.
    Raises 401 if auth fails.
    """
    from app.models.scan import User

    users_present = await _users_exist(db)

    if not users_present:
        # Legacy mode - behave exactly like old verify_api_key
        if not settings.api_key:
            return _LEGACY_ADMIN  # auth disabled
        if key == settings.api_key:
            return _LEGACY_ADMIN
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or missing API key")

    # Multi-user mode
    if not key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Missing X-API-Key header")

    result = await db.execute(select(User).where(User.api_key == key, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or revoked API key")

    return CurrentUser(id=user.id, username=user.username, role=user.role, api_key=user.api_key)


# Keep backward-compat name used as global dependency in main.py
async def verify_api_key(
    key: str | None = Security(_api_key_header),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Global route dependency: raises 401 if not authenticated."""
    await get_current_user(key=key, db=db)


def require_role(*roles: str):
    """
    Returns a FastAPI dependency that enforces role membership.

    Usage:
        @router.post("/scan")
        async def start_scan(
            _: None = Depends(require_role("admin", "analyst")),
            ...
        ):
    """
    allowed: frozenset[str] = frozenset(roles)

    async def _check(
        key: str | None = Security(_api_key_header),
        db: AsyncSession = Depends(get_db),
    ) -> CurrentUser:
        user = await get_current_user(key=key, db=db)
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is not permitted for this action. "
                       f"Required: {sorted(allowed)}",
            )
        return user

    return _check

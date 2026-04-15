"""
Authentication endpoints. These routes are registered WITHOUT the global
verify_api_key dependency so that login and setup remain publicly accessible.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    hash_password, verify_password, generate_api_key,
    get_current_user, require_role, CurrentUser,
)
from app.core.deps import get_db
from app.models.scan import User

router = APIRouter(prefix="/auth", tags=["auth"])

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

VALID_ROLES = {"admin", "analyst", "read-only"}


# ---------- Schemas ----------

class SetupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    api_key: str
    username: str
    role: str


class UserOut(BaseModel):
    id: str
    username: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    total: int
    users: list[UserOut]


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)
    role: str = Field(default="analyst")


class PatchUserRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8)


# ---------- Helpers ----------

async def _users_exist(db: AsyncSession) -> bool:
    result = await db.execute(select(func.count()).select_from(User))
    return (result.scalar_one() or 0) > 0


# ---------- Endpoints ----------

@router.get("/setup-required")
async def setup_required(db: AsyncSession = Depends(get_db)) -> dict:
    """Check whether first-time admin setup is still needed."""
    return {"setup_required": not await _users_exist(db)}


@router.post("/setup", response_model=LoginResponse, status_code=201)
async def setup_first_admin(
    body: SetupRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    Create the first admin user. Only works when no users exist yet.
    After setup, use /auth/users (admin only) to create additional accounts.
    """
    if await _users_exist(db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Setup already complete. Use /auth/users to manage accounts.",
        )

    user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        role="admin",
        api_key=generate_api_key(),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return LoginResponse(api_key=user.api_key, username=user.username, role=user.role)


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Exchange username+password for the user's personal API key."""
    if not await _users_exist(db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No users configured. Complete first-time setup at /auth/setup.",
            headers={"X-Setup-Required": "true"},
        )

    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if not user or not user.is_active or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    return LoginResponse(api_key=user.api_key, username=user.username, role=user.role)


@router.get("/me", response_model=UserOut)
async def get_me(
    key: str | None = Security(_api_key_header),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    """Return the current authenticated user's profile."""
    current = await get_current_user(key=key, db=db)
    result = await db.execute(select(User).where(User.id == current.id))
    user = result.scalar_one_or_none()
    if not user:
        # Legacy mode - return synthetic profile
        return UserOut(
            id="legacy",
            username="legacy",
            role="admin",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            last_login_at=None,
        )
    return UserOut.model_validate(user)


@router.get("/users", response_model=UserListResponse)
async def list_users(
    _: CurrentUser = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    """List all users. Admin only."""
    result = await db.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()
    count_r = await db.execute(select(func.count()).select_from(User))
    total = count_r.scalar_one()
    return UserListResponse(total=total, users=[UserOut.model_validate(u) for u in users])


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    body: CreateUserRequest,
    _: CurrentUser = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    """Create a new user. Admin only."""
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {sorted(VALID_ROLES)}")

    # Check username uniqueness
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        role=body.role,
        api_key=generate_api_key(),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    body: PatchUserRequest,
    current: CurrentUser = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    """Update a user's role, active status, or password. Admin only."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from demoting themselves
    if user_id == current.id and body.role and body.role != "admin":
        raise HTTPException(status_code=400, detail="Cannot change your own role away from admin")

    if body.role is not None:
        if body.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {sorted(VALID_ROLES)}")
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password is not None:
        user.hashed_password = hash_password(body.password)

    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    current: CurrentUser = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deactivate (soft-delete) a user. Admin only. Cannot delete yourself."""
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    await db.commit()

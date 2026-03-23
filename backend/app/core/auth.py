"""
API key authentication dependency.

If API_KEY is set in config, all API routes require the header:
    X-API-Key: <key>

If API_KEY is empty (default), auth is disabled - useful for local dev.
"""
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(key: str | None = Security(_api_key_header)) -> None:
    if not settings.api_key:
        return  # auth disabled
    if key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )

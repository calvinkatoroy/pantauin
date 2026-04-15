"""
Audit logging helper.

Call log_action() from route handlers to record analyst activity.
Writes to a separate DB session - failure is non-fatal and never
propagates to the caller.
"""
import json
import logging

from fastapi import Request

from app.core.deps import AsyncSessionLocal
from app.models.scan import AuditLog

logger = logging.getLogger(__name__)


def _get_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _get_actor(request: Request) -> str:
    key = request.headers.get("X-API-Key", "")
    if not key:
        return "anonymous"
    # Show only last 8 chars to avoid logging secrets
    return f"...{key[-8:]}" if len(key) > 8 else key


async def log_action(
    request: Request,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    extra: dict | None = None,
) -> None:
    """
    Write an audit log entry. Always non-fatal.

    action examples: scan.start, scan.cancel, scan.bulk_start,
                     finding.lifecycle_update, schedule.create,
                     schedule.update, schedule.delete,
                     report.html_download, report.pdf_download
    """
    try:
        async with AsyncSessionLocal() as db:
            entry = AuditLog(
                action=action,
                actor=_get_actor(request),
                ip_address=_get_ip(request),
                resource_type=resource_type,
                resource_id=resource_id,
                extra=json.dumps(extra) if extra else None,
            )
            db.add(entry)
            await db.commit()
    except Exception as exc:
        logger.warning("Audit log write failed for action=%s: %s", action, exc)

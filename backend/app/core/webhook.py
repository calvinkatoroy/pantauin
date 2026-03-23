"""
BSSN/CSIRT webhook notification.

Sends a POST request to WEBHOOK_URL (if configured) when a scan completes
with at least one Critical finding. Failures are logged and silently swallowed
so they never break the scan pipeline.
"""
import logging

import httpx

logger = logging.getLogger(__name__)


async def notify_webhook(webhook_url: str, payload: dict) -> None:
    if not webhook_url:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
            logger.info("Webhook notified: %s → %s", webhook_url, resp.status_code)
    except Exception as exc:
        logger.warning("Webhook notification failed (non-fatal): %s", exc)

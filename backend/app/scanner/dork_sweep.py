"""
Module: dork_sweep
Passive Google CSE dork queries to find gambling-injected pages
in the .go.id / .ac.id namespace.

Contract return shape:
{
    "module": "dork_sweep",
    "status": "success" | "error",
    "findings": [...] | None,
    "error": "..." | None,
}
"""
import logging
import httpx
from app.core.config import settings
from app.scanner.keywords import DORK_QUERIES

logger = logging.getLogger(__name__)

GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"


async def run(domain: str) -> dict:
    if not settings.google_cse_api_key or not settings.google_cse_id:
        logger.warning("Google CSE credentials not configured — dork_sweep skipped")
        return {
            "module": "dork_sweep",
            "status": "success",
            "findings": [],
            "error": "Google CSE API key/ID not configured. Set GOOGLE_CSE_API_KEY and GOOGLE_CSE_ID in .env to enable dork sweep.",
        }

    findings: list[dict] = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        for dork in DORK_QUERIES:
            query = f"site:{domain} {dork}"
            try:
                resp = await client.get(
                    GOOGLE_CSE_URL,
                    params={
                        "key": settings.google_cse_api_key,
                        "cx": settings.google_cse_id,
                        "q": query,
                        "num": 10,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                for item in data.get("items", []):
                    findings.append({
                        "url": item.get("link", ""),
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "dork": dork,
                    })

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning("Google CSE quota exceeded")
                    break
                logger.error("CSE HTTP error for query %s: %s", query, e)
            except Exception as e:
                logger.error("Dork sweep error for query %s: %s", query, e)

    return {
        "module": "dork_sweep",
        "status": "success",
        "findings": findings,
        "error": None,
    }

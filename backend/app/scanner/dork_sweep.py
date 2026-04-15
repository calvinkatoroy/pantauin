"""
Module: dork_sweep
Passive Serper.dev (Google-backed) dork queries to find gambling-injected pages
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

SERPER_URL = "https://google.serper.dev/search"


async def run(domain: str) -> dict:
    if not settings.serper_api_key:
        logger.warning("Serper API key not configured - dork_sweep skipped")
        return {
            "module": "dork_sweep",
            "status": "success",
            "findings": [],
            "error": "Serper API key not configured. Set SERPER_API_KEY in .env to enable dork sweep.",
        }

    findings: list[dict] = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        for dork in DORK_QUERIES:
            query = f"site:{domain} {dork}"
            try:
                resp = await client.post(
                    SERPER_URL,
                    headers={
                        "X-API-KEY": settings.serper_api_key,
                        "Content-Type": "application/json",
                    },
                    json={"q": query, "num": 10},
                )
                resp.raise_for_status()
                data = resp.json()

                for item in data.get("organic", []):
                    findings.append({
                        "url": item.get("link", ""),
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "dork": dork,
                    })

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning("Serper quota exceeded")
                    break
                logger.error(
                    "Serper HTTP error for query %s: %s | body: %s",
                    query, e, e.response.text[:500],
                )
            except Exception as e:
                logger.error("Dork sweep error for query %s: %s", query, e)

    return {
        "module": "dork_sweep",
        "status": "success",
        "findings": findings,
        "error": None,
    }

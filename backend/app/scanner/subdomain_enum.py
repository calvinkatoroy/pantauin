"""
Subdomain enumeration module.

Sources:
  1. Certificate Transparency logs via crt.sh JSON API (passive, no auth needed)
  2. Common subdomain prefix DNS probing (A record lookup)

Returns findings for each live subdomain discovered beyond the root domain.
When settings.subdomain_dispatch_scans is True, a child ScanJob is dispatched
for each live subdomain so the full pipeline runs against it.

Contract:
  run(domain, scan_id) -> {"module": "subdomain_enum", "status": ..., "findings": [...], "error": ...}
"""

import asyncio
import logging
import socket
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Common subdomain prefixes to DNS-probe when crt.sh returns few results
COMMON_PREFIXES = [
    "www", "mail", "ftp", "smtp", "pop", "imap", "webmail",
    "cpanel", "whm", "admin", "portal", "api", "dev", "staging",
    "test", "vpn", "remote", "ns1", "ns2", "mx", "blog", "news",
    "forum", "support", "help", "docs", "cdn", "static", "assets",
    "files", "upload", "download", "m", "mobile", "app", "service",
    "services", "intranet", "internal", "secure", "ssl", "login",
    "auth", "sso", "id", "account", "accounts", "webdav", "owa",
]


def _extract_root(domain: str) -> str:
    """Strip leading www. to get canonical root domain."""
    d = domain.lower().strip()
    if d.startswith("www."):
        d = d[4:]
    return d


async def _crtsh_subdomains(root: str) -> set[str]:
    """Query crt.sh for SANs/CNs matching *.root or root itself."""
    url = f"https://crt.sh/?q=%.{root}&output=json"
    found: set[str] = set()
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return found
            entries = resp.json()
            for entry in entries:
                for name in (entry.get("name_value") or "").splitlines():
                    name = name.strip().lstrip("*.")
                    if name.endswith(f".{root}") or name == root:
                        found.add(name.lower())
    except Exception as e:
        logger.debug("crt.sh query failed for %s: %s", root, e)
    return found


def _dns_resolve(hostname: str) -> str | None:
    """Return IP if hostname resolves, else None. Sync - run in thread."""
    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        return None


async def _resolve(hostname: str) -> str | None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _dns_resolve, hostname)


async def _probe_common_prefixes(root: str) -> set[str]:
    """DNS-probe common prefixes and return those that resolve."""
    candidates = [f"{p}.{root}" for p in COMMON_PREFIXES]
    tasks = [_resolve(c) for c in candidates]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    live: set[str] = set()
    for candidate, ip in zip(candidates, results):
        if isinstance(ip, str):
            live.add(candidate)
    return live


async def run(domain: str, scan_id: str | None = None) -> dict:
    try:
        root = _extract_root(domain)

        # 1. crt.sh passive enumeration
        crt_subs = await _crtsh_subdomains(root)

        # 2. DNS-probe common prefixes for any not already in crt.sh
        prefix_live = await _probe_common_prefixes(root)

        # Combine and deduplicate; exclude the root domain itself
        all_subs: set[str] = (crt_subs | prefix_live) - {root, f"www.{root}"}

        # Resolve crt.sh candidates to filter out dead subdomains
        resolve_tasks = {s: _resolve(s) for s in all_subs}
        resolved = await asyncio.gather(*resolve_tasks.values(), return_exceptions=True)
        live_subs: list[tuple[str, str]] = []
        for sub, ip in zip(resolve_tasks.keys(), resolved):
            if isinstance(ip, str):
                live_subs.append((sub, ip))

        # Cap at subdomain_max
        live_subs = live_subs[: settings.subdomain_max]

        if not live_subs:
            return {
                "module": "subdomain_enum",
                "status": "success",
                "findings": [],
                "error": None,
            }

        # Dispatch child scans if configured
        if settings.subdomain_dispatch_scans and scan_id:
            await _dispatch_child_scans(scan_id, root, live_subs)

        findings = [
            {
                "module": "subdomain_enum",
                "severity": "info",
                "url": f"https://{sub}",
                "title": f"Subdomain discovered: {sub}",
                "description": (
                    f"Live subdomain {sub} resolves to {ip}. "
                    "Source: certificate transparency + DNS probe."
                ),
                "evidence_text": f"DNS A record: {ip}",
                "screenshot_path": None,
                "screenshot_hash": None,
                "detected_keywords": [],
                "injected_links": [],
            }
            for sub, ip in live_subs
        ]

        return {
            "module": "subdomain_enum",
            "status": "success",
            "findings": findings,
            "error": None,
        }

    except Exception as e:
        logger.exception("subdomain_enum error for %s: %s", domain, e)
        return {
            "module": "subdomain_enum",
            "status": "error",
            "findings": [],
            "error": str(e),
        }


async def _dispatch_child_scans(
    parent_scan_id: str, root: str, live_subs: list[tuple[str, str]]
) -> None:
    """Create child ScanJob rows and dispatch Celery tasks for each subdomain."""
    # Import here to avoid circular imports at module load time
    from app.core.deps import AsyncSessionLocal
    from app.models.scan import ScanJob, ModuleStatus
    from app.tasks.scan_tasks import run_scan
    from app.scanner.pipeline import PIPELINE

    async with AsyncSessionLocal() as db:
        for sub, _ip in live_subs:
            job = ScanJob(
                domain=sub,
                status="pending",
                parent_id=parent_scan_id,
            )
            db.add(job)
            await db.flush()

            for mod in PIPELINE:
                db.add(ModuleStatus(scan_job_id=job.id, module=mod.name, status="pending"))

            await db.commit()

            task = run_scan.delay(job.id, sub)
            job.celery_task_id = task.id
            await db.commit()

            logger.info("Dispatched child scan %s for subdomain %s", job.id, sub)

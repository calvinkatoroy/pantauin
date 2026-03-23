"""
Module: path_probe
Non-intrusive GET-only checks for exposed admin panels, config files,
and sensitive paths. Only checks HTTP status codes — no exploitation.

Contract return shape:
{
    "module": "path_probe",
    "status": "success" | "error",
    "findings": [...] | None,
    "error": "..." | None,
}
"""
import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)

# (path, severity, label)
PROBE_PATHS: list[tuple[str, str, str]] = [
    # Critical — sensitive files exposed
    ("/.env", "high", "Exposed .env file"),
    ("/.git/config", "high", "Exposed .git/config"),
    ("/config.php", "high", "Exposed config.php"),
    ("/wp-config.php", "high", "Exposed wp-config.php"),
    ("/configuration.php", "high", "Exposed configuration.php (Joomla)"),
    ("/settings.php", "high", "Exposed settings.php (Drupal)"),
    # Medium — admin panels
    ("/wp-admin/", "medium", "WordPress admin panel exposed"),
    ("/wp-login.php", "medium", "WordPress login page exposed"),
    ("/administrator/", "medium", "Joomla admin panel exposed"),
    ("/phpmyadmin/", "medium", "phpMyAdmin exposed"),
    ("/pma/", "medium", "phpMyAdmin (pma) exposed"),
    ("/admin/", "medium", "Admin panel exposed"),
    ("/login/", "medium", "Login panel exposed"),
    ("/dashboard/", "medium", "Dashboard exposed"),
    # Medium — backup/data dirs
    ("/backup/", "medium", "Backup directory exposed"),
    ("/db/", "medium", "Database directory exposed"),
    ("/sql/", "medium", "SQL directory exposed"),
    ("/dump/", "medium", "Dump directory exposed"),
    # Low — info disclosure
    ("/phpinfo.php", "medium", "phpinfo() page exposed"),
    ("/server-status", "low", "Apache server-status exposed"),
    ("/server-info", "low", "Apache server-info exposed"),
]

EXPOSED_STATUSES = {200, 403}  # 200 = accessible, 403 = exists but blocked


async def _probe(client: httpx.AsyncClient, base_url: str, path: str, severity: str, label: str) -> dict | None:
    url = base_url.rstrip("/") + path
    try:
        resp = await client.get(url)
        if resp.status_code in EXPOSED_STATUSES:
            status_note = "accessible (200)" if resp.status_code == 200 else "exists but blocked (403)"
            return {
                "module": "path_probe",
                "severity": severity if resp.status_code == 200 else "low",
                "url": url,
                "title": f"{label} — {status_note}",
                "description": (
                    f"Path {path} returned HTTP {resp.status_code}. "
                    f"{'This file may contain sensitive credentials or configuration.' if resp.status_code == 200 else 'The resource exists but access is currently restricted.'}"
                ),
                "evidence_text": f"HTTP {resp.status_code} at {url}",
                "screenshot_path": None,
                "screenshot_hash": None,
                "detected_keywords": None,
                "injected_links": None,
            }
    except Exception as e:
        logger.debug("path_probe skip %s: %s", url, e)
    return None


async def run(domain: str) -> dict:
    base_url = f"https://{domain}"

    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=False,  # Don't follow — a 301 means path doesn't exist there
            verify=False,
            headers={"User-Agent": "Pantauin/1.0"},
        ) as client:
            # Quick connectivity check
            try:
                await client.get(base_url)
            except httpx.ConnectError:
                base_url = f"http://{domain}"

            tasks = [
                _probe(client, base_url, path, severity, label)
                for path, severity, label in PROBE_PATHS
            ]
            results = await asyncio.gather(*tasks)

        findings = [r for r in results if r is not None]

        return {
            "module": "path_probe",
            "status": "success",
            "findings": findings,
            "error": None,
        }

    except Exception as e:
        logger.error("path_probe error for %s: %s", domain, e)
        return {
            "module": "path_probe",
            "status": "error",
            "findings": None,
            "error": str(e),
        }

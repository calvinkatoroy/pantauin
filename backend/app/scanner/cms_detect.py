"""
Module: cms_detect
Fingerprint the CMS running on a domain (WordPress, Joomla, Drupal).
Info-level finding - detection only, no vulnerability.

Contract return shape:
{
    "module": "cms_detect",
    "status": "success" | "error",
    "findings": [...] | None,
    "error": "..." | None,
}
"""
import logging
import re
import httpx

logger = logging.getLogger(__name__)


CMS_SIGNATURES: list[dict] = [
    {
        "name": "WordPress",
        "html_patterns": [r"wp-content/", r"wp-includes/"],
        "meta_pattern": r'<meta[^>]+generator[^>]+WordPress',
        "note": "WordPress is the most targeted CMS for .go.id gambling injection. Check WP version and update plugins.",
    },
    {
        "name": "Joomla",
        "html_patterns": [r"/components/com_", r"/modules/mod_"],
        "meta_pattern": r'<meta[^>]+generator[^>]+Joomla',
        "note": "Joomla sites are common targets. Ensure Joomla core and extensions are up to date.",
    },
    {
        "name": "Drupal",
        "html_patterns": [r"sites/default/files/", r"/misc/drupal\.js"],
        "meta_pattern": r'<meta[^>]+generator[^>]+Drupal',
        "note": "Drupal detected. Verify Drupal core version and module security.",
    },
]


async def run(domain: str) -> dict:
    findings: list[dict] = []

    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}"
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                verify=False,
                headers={"User-Agent": "PantauInd/1.0"},
            ) as client:
                resp = await client.get(url)

            html = resp.text
            final_url = str(resp.url)

            for cms in CMS_SIGNATURES:
                detected = False

                # Check HTML patterns
                for pattern in cms["html_patterns"]:
                    if re.search(pattern, html, re.IGNORECASE):
                        detected = True
                        break

                # Check generator meta tag
                if not detected and re.search(cms["meta_pattern"], html, re.IGNORECASE):
                    detected = True

                if detected:
                    # Try to extract version from generator meta
                    version = None
                    version_match = re.search(
                        rf'<meta[^>]+generator[^>]+{cms["name"]}[^"\']*([0-9]+\.[0-9]+[^\s"\']*)',
                        html,
                        re.IGNORECASE,
                    )
                    if version_match:
                        version = version_match.group(1)

                    title = f"{cms['name']} detected"
                    if version:
                        title += f" (version {version})"

                    findings.append({
                        "module": "cms_detect",
                        "severity": "info",
                        "url": final_url,
                        "title": title,
                        "description": cms["note"],
                        "evidence_text": f"CMS: {cms['name']}" + (f" v{version}" if version else ""),
                        "screenshot_path": None,
                        "screenshot_hash": None,
                        "detected_keywords": None,
                        "injected_links": None,
                    })
            break  # Use first successful response

        except httpx.ConnectError:
            if scheme == "https":
                continue
            return {
                "module": "cms_detect",
                "status": "error",
                "findings": None,
                "error": f"Could not connect to {domain}",
            }
        except Exception as e:
            logger.error("cms_detect error for %s: %s", domain, e)
            continue

    return {
        "module": "cms_detect",
        "status": "success",
        "findings": findings,
        "error": None,
    }

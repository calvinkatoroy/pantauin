"""
Module: header_probe
Passive HTTP header analysis via httpx.
Checks for missing security headers, version disclosure, HTTPS enforcement,
and cookie flags.

Contract return shape:
{
    "module": "header_probe",
    "status": "success" | "error",
    "findings": [...] | None,
    "error": "..." | None,
}
"""
import logging
import re
import httpx

logger = logging.getLogger(__name__)

SECURITY_HEADERS = [
    "x-frame-options",
    "x-content-type-options",
    "content-security-policy",
    "strict-transport-security",
    "referrer-policy",
    "permissions-policy",
]

VERSION_HEADERS = ["server", "x-powered-by"]
VERSION_RE = re.compile(r'[\d]+\.[\d]+', re.IGNORECASE)


async def run(domain: str) -> dict:
    findings: list[dict] = []

    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}"
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                verify=False,
            ) as client:
                resp = await client.get(url, headers={"User-Agent": "Pantauin/1.0"})

            headers = {k.lower(): v for k, v in resp.headers.items()}
            final_url = str(resp.url)
            used_https = final_url.startswith("https://")

            # HTTPS enforcement check (only when original request was HTTP)
            if scheme == "http" and not used_https:
                findings.append({
                    "module": "header_probe",
                    "severity": "medium",
                    "url": url,
                    "title": "HTTPS not enforced — site serves over plain HTTP",
                    "description": "The site does not redirect HTTP to HTTPS, exposing traffic to interception.",
                    "evidence_text": None,
                    "screenshot_path": None,
                    "screenshot_hash": None,
                    "detected_keywords": None,
                    "injected_links": None,
                })

            # Missing security headers
            missing = [h for h in SECURITY_HEADERS if h not in headers]
            if missing:
                findings.append({
                    "module": "header_probe",
                    "severity": "low",
                    "url": final_url,
                    "title": f"Missing security headers: {', '.join(missing)}",
                    "description": (
                        f"The following security headers are absent: {', '.join(missing)}. "
                        "These headers mitigate XSS, clickjacking, and MIME-sniffing attacks."
                    ),
                    "evidence_text": f"Missing: {', '.join(missing)}",
                    "screenshot_path": None,
                    "screenshot_hash": None,
                    "detected_keywords": None,
                    "injected_links": None,
                })

            # Version disclosure
            for vh in VERSION_HEADERS:
                if vh in headers:
                    value = headers[vh]
                    if VERSION_RE.search(value):
                        findings.append({
                            "module": "header_probe",
                            "severity": "medium",
                            "url": final_url,
                            "title": f"Version disclosure in {vh.title()} header: {value}",
                            "description": (
                                f"The server exposes version information in the '{vh}' header ({value}). "
                                "This aids attackers in targeting known CVEs."
                            ),
                            "evidence_text": f"{vh}: {value}",
                            "screenshot_path": None,
                            "screenshot_hash": None,
                            "detected_keywords": None,
                            "injected_links": None,
                        })

            # Cookie flags (check Set-Cookie)
            for key, value in resp.headers.items():
                if key.lower() == "set-cookie":
                    missing_flags = []
                    if "secure" not in value.lower():
                        missing_flags.append("Secure")
                    if "httponly" not in value.lower():
                        missing_flags.append("HttpOnly")
                    if "samesite" not in value.lower():
                        missing_flags.append("SameSite")

                    if missing_flags:
                        findings.append({
                            "module": "header_probe",
                            "severity": "low",
                            "url": final_url,
                            "title": f"Cookie missing flags: {', '.join(missing_flags)}",
                            "description": (
                                f"A Set-Cookie header is missing: {', '.join(missing_flags)}. "
                                "This may expose session cookies to theft or CSRF."
                            ),
                            "evidence_text": f"Set-Cookie: {value[:300]}",
                            "screenshot_path": None,
                            "screenshot_hash": None,
                            "detected_keywords": None,
                            "injected_links": None,
                        })
            break  # Only need one successful response

        except httpx.ConnectError:
            if scheme == "https":
                continue  # Try http fallback
            return {
                "module": "header_probe",
                "status": "error",
                "findings": None,
                "error": f"Could not connect to {domain}",
            }
        except Exception as e:
            logger.error("header_probe error for %s: %s", url, e)
            continue

    return {
        "module": "header_probe",
        "status": "success",
        "findings": findings,
        "error": None,
    }

"""
Shodan passive surface probe.

Resolves the target domain to an IP, queries the Shodan host API, and
returns findings for dangerous open ports, known CVEs, and service banners.
Skipped silently if SHODAN_API_KEY is not configured.
"""
import logging
import socket

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Ports considered high-severity if exposed to the internet
_HIGH_SEVERITY_PORTS = {
    3306: "MySQL",
    5432: "PostgreSQL",
    27017: "MongoDB",
    6379: "Redis",
    9200: "Elasticsearch",
    9300: "Elasticsearch cluster",
    11211: "Memcached",
    2375: "Docker daemon (unauthenticated)",
    2376: "Docker daemon (TLS)",
}

_MEDIUM_SEVERITY_PORTS = {
    21: "FTP",
    23: "Telnet",
    25: "SMTP",
    445: "SMB",
    3389: "RDP",
    5900: "VNC",
    8080: "HTTP alternate",
    8443: "HTTPS alternate",
}


def _resolve_ip(domain: str) -> str | None:
    try:
        return socket.getaddrinfo(domain, None)[0][4][0]
    except Exception:
        return None


async def run(domain: str) -> dict:
    if not settings.shodan_api_key:
        return {
            "module": "shodan_probe",
            "status": "skipped",
            "findings": [],
            "error": None,
        }

    ip = _resolve_ip(domain)
    if not ip:
        return {
            "module": "shodan_probe",
            "status": "error",
            "findings": [],
            "error": f"Could not resolve IP for {domain}",
        }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"https://api.shodan.io/shodan/host/{ip}",
                params={"key": settings.shodan_api_key},
            )
            if resp.status_code == 404:
                return {
                    "module": "shodan_probe",
                    "status": "success",
                    "findings": [],
                    "error": None,
                }
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        return {
            "module": "shodan_probe",
            "status": "error",
            "findings": [],
            "error": str(exc),
        }

    findings: list[dict] = []
    open_ports: list[int] = data.get("ports", [])
    cves: list[str] = list(data.get("vulns", {}).keys()) if data.get("vulns") else []
    org: str = data.get("org", "")
    isp: str = data.get("isp", "")

    # Finding: open port inventory (info)
    if open_ports:
        findings.append({
            "module": "shodan_probe",
            "severity": "info",
            "url": f"https://{domain}",
            "title": f"Shodan: {len(open_ports)} open port(s) detected",
            "description": (
                f"IP: {ip} | Org: {org} | ISP: {isp}\n"
                f"Open ports: {', '.join(str(p) for p in sorted(open_ports))}"
            ),
            "evidence_text": f"Shodan data for {ip}",
            "screenshot_path": None,
            "screenshot_hash": None,
            "detected_keywords": [],
            "injected_links": [],
        })

    # High-severity exposed ports
    for port in open_ports:
        if port in _HIGH_SEVERITY_PORTS:
            service = _HIGH_SEVERITY_PORTS[port]
            findings.append({
                "module": "shodan_probe",
                "severity": "high",
                "url": f"https://{domain}",
                "title": f"Shodan: {service} exposed on port {port}",
                "description": (
                    f"Port {port} ({service}) is publicly accessible on {ip}. "
                    f"Database/cache services should not be exposed to the internet."
                ),
                "evidence_text": f"IP: {ip}, Port: {port}, Service: {service}",
                "screenshot_path": None,
                "screenshot_hash": None,
                "detected_keywords": [],
                "injected_links": [],
            })
        elif port in _MEDIUM_SEVERITY_PORTS:
            service = _MEDIUM_SEVERITY_PORTS[port]
            findings.append({
                "module": "shodan_probe",
                "severity": "medium",
                "url": f"https://{domain}",
                "title": f"Shodan: {service} exposed on port {port}",
                "description": (
                    f"Port {port} ({service}) is publicly accessible on {ip}."
                ),
                "evidence_text": f"IP: {ip}, Port: {port}, Service: {service}",
                "screenshot_path": None,
                "screenshot_hash": None,
                "detected_keywords": [],
                "injected_links": [],
            })

    # CVEs from Shodan
    for cve_id in cves[:10]:  # cap at 10 CVEs per finding
        vuln_data = data.get("vulns", {}).get(cve_id, {})
        cvss = vuln_data.get("cvss", 0.0) or 0.0
        severity = "critical" if cvss >= 9.0 else "high" if cvss >= 7.0 else "medium"
        findings.append({
            "module": "shodan_probe",
            "severity": severity,
            "url": f"https://{domain}",
            "title": f"Shodan: {cve_id} (CVSS {cvss})",
            "description": vuln_data.get("summary", f"CVE {cve_id} detected by Shodan on {ip}"),
            "evidence_text": f"CVE: {cve_id}, CVSS: {cvss}, IP: {ip}",
            "screenshot_path": None,
            "screenshot_hash": None,
            "detected_keywords": [],
            "injected_links": [],
        })

    return {
        "module": "shodan_probe",
        "status": "success",
        "findings": findings,
        "error": None,
    }

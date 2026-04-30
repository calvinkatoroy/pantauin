"""
Step 4 - Passive Attack Surface Profiling

Input:   data/raw/domains.csv              (ALL domains - clean domains are the control group)
Output:  data/processed/attack_surface.csv
Resume:  data/checkpoints/surface.txt      (one domain per line)

Per domain (httpx GET only, concurrency = SURFACE_CONCURRENCY = 30):

  HTTPS / SSL:
    - HTTP -> HTTPS redirect present?
    - SSL certificate valid (stdlib ssl handshake)?
    - SSL certificate expiring within 30 days?

  Security headers (boolean: header present in response?):
    Content-Security-Policy, Strict-Transport-Security, X-Frame-Options,
    X-Content-Type-Options, Referrer-Policy, Permissions-Policy, X-XSS-Protection

  Version disclosure (boolean + raw value):
    - Server header: contains version string? (e.g. Apache/2.4.41)
    - X-Powered-By header: present at all? (e.g. PHP/7.4.3)
    - X-AspNet-Version header: present?

  CMS fingerprinting (from HTML body patterns):
    - WordPress: wp-content, wp-includes, /wp-json/
    - Joomla: /components/com_, Joomla generator meta
    - Drupal: Drupal.settings, sites/default/files

  Exposed sensitive paths (GET-only, 200 or 403 = exposed):
    All paths in EXPOSED_PATHS, probed in parallel per domain

  Cookie security (from Set-Cookie response header):
    - HttpOnly flag?
    - Secure flag?
    - SameSite attribute?

Output columns: one row per domain, all features as boolean/string columns.

PASSIVE ONLY - GET requests only, no POST, no payload injection of any kind.
"""

import asyncio
import logging
import re
import socket
import ssl
import warnings
from pathlib import Path

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm

import research.config as cfg

log = logging.getLogger(__name__)
warnings.filterwarnings("ignore", message=".*SSL.*")

CHECKPOINT_FILE = cfg.DATA_CHECKPOINTS / "surface.txt"

FIELDNAMES = [
    "domain",
    # HTTPS / SSL
    "https_enforced",
    "ssl_valid",
    "ssl_expiring_soon",
    # Security headers
    "header_csp",
    "header_hsts",
    "header_x_frame_options",
    "header_x_content_type_options",
    "header_referrer_policy",
    "header_permissions_policy",
    "header_x_xss_protection",
    # Version disclosure
    "server_header",           # raw value (empty if no version detected)
    "x_powered_by",            # raw value (empty if not present)
    "x_aspnet_version",        # raw value (empty if not present)
    "has_server_disclosure",   # bool: version string found in Server header
    "has_x_powered_by",        # bool: header present
    "has_x_aspnet_version",    # bool: header present
    # CMS
    "cms",                     # wordpress | joomla | drupal | unknown
    "cms_version",             # generator meta value if found
    # Cookie security (False if no Set-Cookie header present)
    "cookie_httponly",
    "cookie_secure",
    "cookie_samesite",
    # Exposed paths
    "exposed_paths",           # pipe-separated list
    "exposed_path_count",
    "has_exposed_path",        # bool convenience
    # Meta
    "probed_at",
]

# CMS fingerprint patterns (checked against raw HTML)
_CMS_PATTERNS: dict[str, re.Pattern] = {
    "wordpress": re.compile(r"wp-content|wp-includes|/wp-json/", re.IGNORECASE),
    "joomla":    re.compile(r"/components/com_|/media/jui/|Joomla!", re.IGNORECASE),
    "drupal":    re.compile(r"Drupal\.settings|sites/default/files", re.IGNORECASE),
}

# Version string in Server / X-Powered-By headers
_VERSION_RE = re.compile(
    r"(Apache|nginx|LiteSpeed|PHP|OpenSSL|Microsoft-IIS|Tomcat|Cherokee)"
    r"[/\s]+([\d.]+)",
    re.IGNORECASE,
)

# Generator meta tag extraction
_GENERATOR_RE = re.compile(
    r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def _load_checkpoint() -> set[str]:
    if not CHECKPOINT_FILE.exists():
        return set()
    return {ln.strip() for ln in CHECKPOINT_FILE.read_text("utf-8").splitlines() if ln.strip()}


def _append_checkpoint(domain: str) -> None:
    with CHECKPOINT_FILE.open("a", encoding="utf-8") as f:
        f.write(domain + "\n")


# ---------------------------------------------------------------------------
# SSL check (blocking, runs in thread pool via asyncio.to_thread)
# ---------------------------------------------------------------------------

def _check_ssl_sync(domain: str) -> tuple[bool, bool]:
    """
    Perform a TLS handshake to check certificate validity and expiry.

    Args:
        domain: Hostname to connect to on port 443.

    Returns:
        Tuple of (ssl_valid, ssl_expiring_within_30_days).
        Both False on connection failure or invalid cert.
    """
    from datetime import datetime, timezone

    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                not_after = cert.get("notAfter", "")
                if not not_after:
                    return True, False
                expiry = datetime.strptime(
                    not_after, "%b %d %H:%M:%S %Y %Z"
                ).replace(tzinfo=timezone.utc)
                days = (expiry - datetime.now(timezone.utc)).days
                return True, days <= 30
    except ssl.SSLCertVerificationError:
        return False, False
    except (socket.timeout, socket.gaierror, OSError, ConnectionRefusedError):
        return False, False
    except Exception:
        return False, False


# ---------------------------------------------------------------------------
# CMS detection
# ---------------------------------------------------------------------------

def _detect_cms(html: str) -> tuple[str, str]:
    """
    Fingerprint CMS from HTML body patterns and generator meta tag.

    Args:
        html: Raw HTML string.

    Returns:
        Tuple of (cms_name, version_string_or_empty).
    """
    for name, pattern in _CMS_PATTERNS.items():
        if pattern.search(html):
            gen = _GENERATOR_RE.search(html)
            version = gen.group(1) if gen else ""
            return name, version
    return "unknown", ""


# ---------------------------------------------------------------------------
# Cookie flag parsing
# ---------------------------------------------------------------------------

def _parse_cookie_flags(resp: httpx.Response) -> tuple[bool, bool, bool]:
    """
    Extract HttpOnly, Secure, and SameSite flags from Set-Cookie headers.

    Args:
        resp: httpx Response object.

    Returns:
        Tuple of (httponly, secure, samesite) booleans.
        All False if no Set-Cookie header is present.
    """
    cookie_headers = [
        v for k, v in resp.headers.items() if k.lower() == "set-cookie"
    ]
    if not cookie_headers:
        return False, False, False

    combined = " ".join(cookie_headers).lower()
    httponly = "httponly" in combined
    secure   = bool(re.search(r";\s*secure(?:\s*;|$)", combined))
    samesite = "samesite=" in combined
    return httponly, secure, samesite


# ---------------------------------------------------------------------------
# Exposed path probe
# ---------------------------------------------------------------------------

async def _probe_path(client: httpx.AsyncClient, domain: str, path: str) -> str | None:
    """
    Probe a single path.  Returns path string if 200 or 403, else None.

    Args:
        client: Shared httpx async client.
        domain: Domain to probe.
        path:   URL path to check (e.g. "/.env").

    Returns:
        The path string if accessible, None otherwise.
    """
    for scheme in ("https", "http"):
        try:
            resp = await client.get(
                f"{scheme}://{domain}{path}", follow_redirects=False
            )
            if resp.status_code in (200, 403):
                return path
            break  # path probed, not exposed on https; no need for http fallback
        except Exception:
            if scheme == "https":
                continue
    return None


# ---------------------------------------------------------------------------
# Per-domain worker
# ---------------------------------------------------------------------------

async def _probe_surface(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    domain: str,
    csv_path: Path,
    lock: asyncio.Lock,
) -> None:
    """
    Collect all attack surface features for one domain.

    Args:
        client:   Shared httpx async client.
        semaphore: Concurrency limiter.
        domain:   Domain to probe.
        csv_path: Path to attack_surface.csv for appending.
        lock:     Asyncio lock protecting CSV writes.
    """
    async with semaphore:
        row: dict = {
            "domain":                   domain,
            "https_enforced":           False,
            "ssl_valid":                False,
            "ssl_expiring_soon":        False,
            "header_csp":               False,
            "header_hsts":              False,
            "header_x_frame_options":   False,
            "header_x_content_type_options": False,
            "header_referrer_policy":   False,
            "header_permissions_policy": False,
            "header_x_xss_protection":  False,
            "server_header":            "",
            "x_powered_by":             "",
            "x_aspnet_version":         "",
            "has_server_disclosure":    False,
            "has_x_powered_by":         False,
            "has_x_aspnet_version":     False,
            "cms":                      "unknown",
            "cms_version":              "",
            "cookie_httponly":          False,
            "cookie_secure":            False,
            "cookie_samesite":          False,
            "exposed_paths":            "",
            "exposed_path_count":       0,
            "has_exposed_path":         False,
            "probed_at":                cfg.now_wib(),
        }

        # --- Main page: headers, HTTPS enforcement, CMS ---
        for scheme in ("https", "http"):
            try:
                resp = await client.get(
                    f"{scheme}://{domain}", follow_redirects=True
                )
                hdrs = {k.lower(): v for k, v in resp.headers.items()}

                row["https_enforced"] = str(resp.url).startswith("https://")

                row["header_csp"]                     = "content-security-policy" in hdrs
                row["header_hsts"]                    = "strict-transport-security" in hdrs
                row["header_x_frame_options"]         = "x-frame-options" in hdrs
                row["header_x_content_type_options"]  = "x-content-type-options" in hdrs
                row["header_referrer_policy"]         = "referrer-policy" in hdrs
                row["header_permissions_policy"]      = "permissions-policy" in hdrs
                row["header_x_xss_protection"]        = "x-xss-protection" in hdrs

                server  = hdrs.get("server", "")
                xpb     = hdrs.get("x-powered-by", "")
                xaspnet = hdrs.get("x-aspnet-version", "")
                row["server_header"]        = server
                row["x_powered_by"]         = xpb
                row["x_aspnet_version"]     = xaspnet
                row["has_server_disclosure"] = bool(_VERSION_RE.search(server))
                row["has_x_powered_by"]      = bool(xpb)
                row["has_x_aspnet_version"]  = bool(xaspnet)

                # Cookie flags
                row["cookie_httponly"], row["cookie_secure"], row["cookie_samesite"] = (
                    _parse_cookie_flags(resp)
                )

                # CMS from HTML
                if resp.status_code == 200:
                    ct = resp.headers.get("content-type", "")
                    if "text" in ct or "html" in ct:
                        row["cms"], row["cms_version"] = _detect_cms(resp.text)

                break  # success on this scheme, no need to try http fallback

            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
                if scheme == "https":
                    continue
            except Exception as exc:
                log.debug("Main probe failed %s (%s): %s", domain, scheme, exc)
                break

        # --- SSL check (blocking, offloaded to thread) ---
        try:
            ssl_valid, ssl_expiring = await asyncio.to_thread(_check_ssl_sync, domain)
            row["ssl_valid"]         = ssl_valid
            row["ssl_expiring_soon"] = ssl_expiring
        except Exception as exc:
            log.debug("SSL check thread error for %s: %s", domain, exc)

        # --- Exposed path probing (all paths in parallel within domain) ---
        path_results = await asyncio.gather(
            *[_probe_path(client, domain, p) for p in cfg.EXPOSED_PATHS],
            return_exceptions=True,
        )
        exposed = [p for p in path_results if isinstance(p, str)]
        row["exposed_paths"]      = "|".join(exposed)
        row["exposed_path_count"] = len(exposed)
        row["has_exposed_path"]   = len(exposed) > 0

        async with lock:
            pd.DataFrame([row]).to_csv(
                str(csv_path), mode="a", header=False, index=False, lineterminator="\n"
            )
            _append_checkpoint(domain)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def profile_attack_surface(limit: int = 0) -> None:
    """
    Profile passive attack surface for all domains from domains.csv.

    Clean domains (not in suspected/confirmed) are essential as the control
    group for chi-square and logistic regression in the analysis step.

    Args:
        limit: If > 0, process only first N domains.
    """
    if not cfg.DOMAINS_CSV.exists():
        raise FileNotFoundError(
            f"{cfg.DOMAINS_CSV} not found - run `enumerate` first."
        )

    df_domains = pd.read_csv(cfg.DOMAINS_CSV, dtype=str)
    all_domains = df_domains["domain"].dropna().tolist()

    if limit:
        all_domains = all_domains[:limit]

    done = _load_checkpoint()
    pending = [d for d in all_domains if d not in done]

    log.info(
        "surface: %d total | %d already done | %d pending",
        len(all_domains), len(done), len(pending),
    )
    if not pending:
        log.info("Nothing to do - all domains already profiled.")
        return

    csv_path = cfg.ATTACK_SURFACE_CSV
    if not done:
        pd.DataFrame(columns=FIELDNAMES).to_csv(
            str(csv_path), index=False, lineterminator="\n"
        )

    semaphore = asyncio.Semaphore(cfg.SURFACE_CONCURRENCY)
    lock = asyncio.Lock()

    limits = httpx.Limits(
        max_connections=cfg.SURFACE_CONCURRENCY + 20,
        max_keepalive_connections=20,
    )
    async with httpx.AsyncClient(
        timeout=cfg.HTTP_TIMEOUT,
        headers={"User-Agent": cfg.USER_AGENT},
        limits=limits,
        verify=False,
    ) as client:
        tasks = [
            _probe_surface(client, semaphore, d, csv_path, lock)
            for d in pending
        ]
        pbar = tqdm(
            total=len(tasks), desc="Profiling surface", unit="domain", dynamic_ncols=True
        )
        for coro in asyncio.as_completed(tasks):
            await coro
            pbar.update(1)
        pbar.close()

    # Summary
    df_out = pd.read_csv(csv_path)
    n_wp    = int((df_out["cms"] == "wordpress").sum())
    n_exp   = int(df_out["has_exposed_path"].astype(str).str.lower().eq("true").sum())
    n_nodis = int((~df_out["header_csp"].astype(str).str.lower().eq("true")).sum())
    log.info(
        "Surface profiling complete: %d profiled | WordPress: %d | Exposed path: %d | No CSP: %d",
        len(df_out), n_wp, n_exp, n_nodis,
    )
    log.info("Results -> %s", csv_path)

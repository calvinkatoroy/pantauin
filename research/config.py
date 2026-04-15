"""
Central configuration for the PantauInd research pipeline.

All paths, concurrency limits, keyword lists, probe targets, and statistical
parameters live here. Pipeline modules import from this module; do not
hardcode paths or constants in the pipeline files.

Environment variable RESEARCH_DATA_DIR overrides the default data/ location.
Set it before importing any pipeline module (cli.py handles this via --output-dir).
"""

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# WIB timezone (UTC+7) - all timestamps in the pipeline use this
# ---------------------------------------------------------------------------
WIB = timezone(timedelta(hours=7))


def now_wib() -> str:
    """Return current timestamp in WIB as ISO 8601 string (seconds precision)."""
    return datetime.now(WIB).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Directory structure
# Read RESEARCH_DATA_DIR from env so --output-dir in cli.py can override.
# ---------------------------------------------------------------------------
_DEFAULT_DATA = str(Path(__file__).parent / "data")
DATA_DIR = Path(os.environ.get("RESEARCH_DATA_DIR", _DEFAULT_DATA))

DATA_RAW        = DATA_DIR / "raw"          # domains.csv from crt.sh
DATA_INTERIM    = DATA_DIR / "interim"      # suspected.csv
DATA_PROCESSED  = DATA_DIR / "processed"    # confirmed.csv, attack_surface.csv
DATA_EVIDENCE   = DATA_DIR / "evidence"     # Playwright screenshots
DATA_TABLES     = DATA_DIR / "tables"       # CSV + LaTeX tables
DATA_FIGURES    = DATA_DIR / "figures"      # PNG figures
DATA_CHECKPOINTS = DATA_DIR / "checkpoints" # per-step resume files


def ensure_dirs() -> None:
    """Create all data directories.  Called once at pipeline startup."""
    for d in (
        DATA_RAW, DATA_INTERIM, DATA_PROCESSED, DATA_EVIDENCE,
        DATA_TABLES, DATA_FIGURES, DATA_CHECKPOINTS,
    ):
        d.mkdir(parents=True, exist_ok=True)


ensure_dirs()

# ---------------------------------------------------------------------------
# Output CSV paths (derived from dir constants above)
# ---------------------------------------------------------------------------
DOMAINS_CSV       = DATA_RAW       / "domains.csv"
SUSPECTED_CSV     = DATA_INTERIM   / "suspected.csv"
CONFIRMED_CSV     = DATA_PROCESSED / "confirmed.csv"
ATTACK_SURFACE_CSV = DATA_PROCESSED / "attack_surface.csv"

# ---------------------------------------------------------------------------
# Target TLDs
# ---------------------------------------------------------------------------
TARGET_TLDS: list[str] = ["go.id", "ac.id"]

# crt.sh query URLs - one per TLD
CRTSH_URLS: dict[str, str] = {
    "go.id": "https://crt.sh/?q=%25.go.id&output=json",
    "ac.id": "https://crt.sh/?q=%25.ac.id&output=json",
}

# ---------------------------------------------------------------------------
# Gambling keywords (Bahasa Indonesia + common variants)
# Used in detect (httpx+BS4) and confirm (Playwright) steps.
# Ordered roughly by severity/confidence of infection signal.
# ---------------------------------------------------------------------------
GAMBLING_KEYWORDS: list[str] = [
    # Multi-word high-confidence phrases
    "slot gacor", "slot online", "judi online", "judi bola", "judi slot",
    "togel online", "situs judi", "agen judi", "bandar judi",
    "poker online", "casino online", "taruhan online", "taruhan bola",
    "bocoran slot", "rtp slot", "rtp live", "link slot", "daftar slot",
    "login slot", "deposit slot", "agen slot", "link alternatif",
    "toto slot", "mahjong ways", "sweet bonanza", "gates of olympus",
    "starlight princess", "pg soft", "pragmatic play",
    # High-signal single words
    "sbobet", "togel", "toto", "maxwin", "jackpot", "scatter",
    "gacor", "judi", "taruhan", "bandar",
    # Common game names / brand injections
    "zeus slot", "mahjong", "habanero",
    # Common anchor-stuffed number patterns (used in hidden links)
    "slot138", "slot777", "slot303", "slot88", "slot99",
    # SGP/HK lottery terms
    "4d", "3d", "2d", "sgp", "sydney", "sdy", "hk togel", "live draw",
    # English crossover terms
    "sportsbook", "betting", "online casino",
]

# ---------------------------------------------------------------------------
# Network settings
# ---------------------------------------------------------------------------
DETECT_CONCURRENCY   = 50   # httpx async workers for step 2 (detect)
SURFACE_CONCURRENCY  = 30   # httpx async workers for step 4 (surface)
                             # Lower than detect: each domain hits more endpoints
PLAYWRIGHT_CONCURRENCY = 8  # Playwright pages for step 3 (confirm)
                             # Memory-bound: ~150MB/page; 8 = ~1.2GB safe on 16GB RAM

HTTP_TIMEOUT      = 10      # seconds per httpx request
PLAYWRIGHT_TIMEOUT = 20_000 # milliseconds per Playwright navigation

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Exposed paths to probe in step 4 (GET-only, no payload injection)
# 200 or 403 response = path is exposed / potentially accessible
# ---------------------------------------------------------------------------
EXPOSED_PATHS: list[str] = [
    "/.env",
    "/.git/config",
    "/.htaccess",
    "/wp-admin/",
    "/wp-login.php",
    "/wp-config.php.bak",
    "/xmlrpc.php",
    "/administrator/",       # Joomla
    "/phpmyadmin/",
    "/admin/",
    "/backup/",
    "/config.php",
    "/server-status",        # Apache mod_status
    "/elmah.axd",            # ASP.NET error log
    "/trace.axd",            # ASP.NET trace
    "/installer/",           # Joomla installer
]

# ---------------------------------------------------------------------------
# Security response headers checked in step 4
# Stored as lowercase names to match against lowercased response headers.
# ---------------------------------------------------------------------------
SECURITY_HEADERS: list[str] = [
    "content-security-policy",
    "strict-transport-security",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
    "permissions-policy",
    "x-xss-protection",
]

# ---------------------------------------------------------------------------
# Analysis: binary feature columns used in chi-square + logistic regression
# Must match column names in attack_surface.csv exactly.
# ---------------------------------------------------------------------------
BINARY_FEATURES: list[str] = [
    # HTTPS / SSL
    "https_enforced",
    "ssl_valid",
    "ssl_expiring_soon",
    # Security headers (True = header present)
    "header_csp",
    "header_hsts",
    "header_x_frame_options",
    "header_x_content_type_options",
    "header_referrer_policy",
    "header_permissions_policy",
    "header_x_xss_protection",
    # Version disclosure (True = version string detected in header)
    "has_server_disclosure",
    "has_x_powered_by",
    "has_x_aspnet_version",
    # Exposed paths
    "has_exposed_path",
    # CMS (derived from cms column)
    "cms_wordpress",
    "cms_joomla",
    "cms_drupal",
    # Cookie security (True = flag present in at least one Set-Cookie)
    "cookie_httponly",
    "cookie_secure",
    "cookie_samesite",
]

# Human-readable labels for BINARY_FEATURES (used in tables + figures)
FEATURE_LABELS: dict[str, str] = {
    "https_enforced":               "HTTPS Enforced",
    "ssl_valid":                    "SSL Certificate Valid",
    "ssl_expiring_soon":            "SSL Expiring <= 30 Days",
    "header_csp":                   "Content-Security-Policy",
    "header_hsts":                  "Strict-Transport-Security (HSTS)",
    "header_x_frame_options":       "X-Frame-Options",
    "header_x_content_type_options":"X-Content-Type-Options",
    "header_referrer_policy":       "Referrer-Policy",
    "header_permissions_policy":    "Permissions-Policy",
    "header_x_xss_protection":      "X-XSS-Protection",
    "has_server_disclosure":        "Server Version Disclosure",
    "has_x_powered_by":             "X-Powered-By Disclosed",
    "has_x_aspnet_version":         "X-AspNet-Version Disclosed",
    "has_exposed_path":             "Exposed Sensitive Path",
    "cms_wordpress":                "CMS: WordPress",
    "cms_joomla":                   "CMS: Joomla",
    "cms_drupal":                   "CMS: Drupal",
    "cookie_httponly":              "Cookie: HttpOnly",
    "cookie_secure":                "Cookie: Secure",
    "cookie_samesite":              "Cookie: SameSite",
}

# ---------------------------------------------------------------------------
# Statistical analysis parameters
# ---------------------------------------------------------------------------
ALPHA = 0.05  # Per-test significance threshold (Bonferroni correction applied separately)
VIF_THRESHOLD = 10.0  # Flag features with VIF above this as multicollinear

"""
Step 2 - Lightweight Bulk Gambling Content Detection

Input:   data/raw/domains.csv           (from step 1)
Output:  data/interim/suspected.csv
Resume:  data/checkpoints/detect.txt    (one domain per line)

Per domain (httpx + BeautifulSoup, async, concurrency = DETECT_CONCURRENCY):
  - Fetch root URL: HTTPS first, HTTP fallback
  - Extract page text (strip script/style/noscript)
  - Match GAMBLING_KEYWORDS in: visible body text, page title,
    meta description, meta keywords
  - Detect hidden anchor tags (display:none, visibility:hidden, opacity:0,
    off-screen position) containing gambling signals
  - Detect suspicious external iframes
  - False-positive filter: if keywords appear ONLY inside <nav>/<footer>/
    <header>/<aside>, keyword_hits is set to 0 and detection_reason is
    "nav_footer_only" - these domains do not proceed to confirm step
  - Write ALL domains to suspected.csv (keyword_hits=0 = clean/undetected)

Output columns:
  domain, url_fetched, status_code, keyword_hits, keyword_list,
  hidden_links_found, iframe_found, detection_reason, scanned_at

SSL verification is disabled: many .go.id sites have expired or self-signed
certificates unrelated to infection status.
"""

import asyncio
import logging
import re
import warnings
from typing import NamedTuple

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm

import research.config as cfg

log = logging.getLogger(__name__)
warnings.filterwarnings("ignore", message=".*SSL.*")
warnings.filterwarnings("ignore", category=DeprecationWarning)

CHECKPOINT_FILE = cfg.DATA_CHECKPOINTS / "detect.txt"

FIELDNAMES = [
    "domain",
    "url_fetched",
    "status_code",
    "keyword_hits",
    "keyword_list",
    "hidden_links_found",
    "iframe_found",
    "detection_reason",
    "scanned_at",
]

# Compile keyword patterns once at import time
_KW_PATTERNS = [
    re.compile(re.escape(kw), re.IGNORECASE) for kw in cfg.GAMBLING_KEYWORDS
]

# Gambling signal for anchor text / iframe src (single-word patterns)
_GAMBLING_SIGNAL = re.compile(
    r"(slot|judi|togel|casino|betting|poker|gacor|maxwin|sbobet|scatter|toto|zeus)",
    re.IGNORECASE,
)

# Hidden CSS patterns on anchor tags
_HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none"
    r"|visibility\s*:\s*hidden"
    r"|opacity\s*:\s*0(?:[^.]|$)"
    r"|(left|top)\s*:\s*-\d{3,}px"
    r"|(width|height)\s*:\s*0\s*(px|em|rem)?(?:\s*;|$)",
    re.IGNORECASE,
)

# Trusted domains for iframe allow-list (don't flag these)
_TRUSTED_IFRAME_HOSTS = frozenset(
    ["youtube.com", "youtu.be", "google.com", "maps.google.com",
     "facebook.com", "twitter.com", "instagram.com",
     "go.id", "ac.id"]
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
# Keyword matching
# ---------------------------------------------------------------------------

def _match_keywords(text: str) -> list[str]:
    """
    Return list of GAMBLING_KEYWORDS that appear in text (case-insensitive).

    Args:
        text: Plaintext string to search.

    Returns:
        Deduplicated list of matched keyword strings.
    """
    return [
        cfg.GAMBLING_KEYWORDS[i]
        for i, pat in enumerate(_KW_PATTERNS)
        if pat.search(text)
    ]


# ---------------------------------------------------------------------------
# Hidden link + iframe detection
# ---------------------------------------------------------------------------

def _find_hidden_gambling_links(soup: BeautifulSoup) -> int:
    """
    Count anchor tags that are visually hidden AND contain gambling signals.

    Hidden is defined as: inline CSS sets display:none, visibility:hidden,
    opacity:0, or positions the element far off-screen (< -200px).

    Args:
        soup: Parsed BeautifulSoup tree (with scripts already removed).

    Returns:
        Count of hidden gambling anchor tags found.
    """
    count = 0
    for a in soup.find_all("a", href=True):
        style = a.get("style", "")
        if not _HIDDEN_STYLE.search(style):
            continue
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if _GAMBLING_SIGNAL.search(href) or _GAMBLING_SIGNAL.search(text):
            count += 1
    return count


def _find_suspicious_iframes(soup: BeautifulSoup) -> int:
    """
    Count iframes whose src points to non-trusted external domains.

    Args:
        soup: Parsed BeautifulSoup tree.

    Returns:
        Count of suspicious iframe tags.
    """
    count = 0
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "").strip()
        if not src or src.startswith("data:"):
            continue
        # Must be external (http/https or protocol-relative)
        if not (src.startswith("http") or src.startswith("//")):
            continue
        # Check against allow-list
        if any(host in src for host in _TRUSTED_IFRAME_HOSTS):
            continue
        count += 1
    return count


# ---------------------------------------------------------------------------
# False-positive filter
# ---------------------------------------------------------------------------

def _keywords_only_in_chrome(
    soup: BeautifulSoup, matched: list[str]
) -> bool:
    """
    Return True if ALL keyword matches appear only inside nav/footer/header/aside.

    This filters sites where gambling terms appear in navigation links that
    are present on every page of a legitimate site, not as injected content.

    Args:
        soup: Parsed BeautifulSoup tree (scripts already removed).
        matched: List of matched keyword strings.

    Returns:
        True if keywords are only in site chrome (nav/footer), False otherwise.
    """
    if not matched:
        return False

    # Deep-copy by re-serialising (BS4 has no .copy())
    soup2 = BeautifulSoup(str(soup), "lxml")
    for tag in soup2(["nav", "footer", "header", "aside", "menu"]):
        tag.decompose()

    body_text = soup2.get_text(" ", strip=True)
    # If any keyword still appears outside chrome, it's NOT a false positive
    return not any(
        re.search(re.escape(kw), body_text, re.IGNORECASE) for kw in matched
    )


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

async def _fetch_page(
    client: httpx.AsyncClient, domain: str
) -> tuple[str, str, int, str]:
    """
    Fetch root page.  Try HTTPS then HTTP.

    Args:
        client: Shared httpx async client.
        domain: Domain name without scheme.

    Returns:
        Tuple of (final_url, html, status_code, error_hint).
        On total failure: ("", "", -1, "error description").
    """
    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}"
        try:
            resp = await client.get(url, follow_redirects=True)
            ct = resp.headers.get("content-type", "")
            if resp.status_code == 200 and ("text" in ct or "html" in ct):
                return str(resp.url), resp.text, resp.status_code, ""
            return str(resp.url), "", resp.status_code, ""
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
            continue
        except httpx.TooManyRedirects:
            return url, "", -1, "too_many_redirects"
        except Exception as exc:
            log.debug("fetch %s (%s): %s", domain, scheme, exc)
            break

    return "", "", -1, "unreachable"


# ---------------------------------------------------------------------------
# Per-domain worker
# ---------------------------------------------------------------------------

async def _process_domain(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    domain: str,
    csv_path,
    lock: asyncio.Lock,
) -> None:
    """
    Fetch, parse, and analyse one domain.  Write result row to CSV.

    Args:
        client:    Shared httpx async client.
        semaphore: Concurrency limiter.
        domain:    Domain to scan.
        csv_path:  Path to suspected.csv for appending.
        lock:      Asyncio lock protecting CSV writes.
    """
    async with semaphore:
        final_url, html, status, error = await _fetch_page(client, domain)

        row = {
            "domain":           domain,
            "url_fetched":      final_url or f"https://{domain}",
            "status_code":      status,
            "keyword_hits":     0,
            "keyword_list":     "",
            "hidden_links_found": 0,
            "iframe_found":     0,
            "detection_reason": error or "no_content",
            "scanned_at":       cfg.now_wib(),
        }

        if html:
            soup = BeautifulSoup(html, "lxml")

            # Remove noise tags before text extraction
            for noise in soup(["script", "style", "noscript", "template"]):
                noise.decompose()

            # --- Meta tag content ---
            title_el = soup.find("title")
            meta_desc_el = soup.find("meta", attrs={"name": re.compile("description", re.I)})
            meta_kw_el   = soup.find("meta", attrs={"name": re.compile("keywords", re.I)})

            meta_text = " ".join(filter(None, [
                title_el.get_text(strip=True)           if title_el      else "",
                meta_desc_el.get("content", "")         if meta_desc_el  else "",
                meta_kw_el.get("content", "")           if meta_kw_el    else "",
            ]))

            # --- Visible body text ---
            body_text = soup.get_text(" ", strip=True)

            # --- Combined search surface ---
            full_text = body_text + " " + meta_text
            all_matched = _match_keywords(full_text)

            # --- False positive filter ---
            in_chrome_only = _keywords_only_in_chrome(soup, all_matched)
            if in_chrome_only and all_matched:
                row["keyword_hits"]     = 0
                row["keyword_list"]     = ""
                row["detection_reason"] = "nav_footer_only"
            else:
                row["keyword_hits"]  = len(all_matched)
                row["keyword_list"]  = "|".join(all_matched)

            # --- Hidden links + iframes (always checked) ---
            row["hidden_links_found"] = _find_hidden_gambling_links(soup)
            row["iframe_found"]       = _find_suspicious_iframes(soup)

            # --- Detection reason (override if content found) ---
            if row["keyword_hits"] > 0:
                row["detection_reason"] = "keyword_match"
            if row["hidden_links_found"] > 0:
                row["detection_reason"] = (
                    "hidden_links" if row["keyword_hits"] == 0
                    else row["detection_reason"] + "+hidden_links"
                )
            if row["iframe_found"] > 0 and row["detection_reason"] == "no_content":
                row["detection_reason"] = "suspicious_iframe"
            if row["detection_reason"] == "no_content" and status == 200:
                row["detection_reason"] = "clean"

        async with lock:
            pd.DataFrame([row]).to_csv(
                str(csv_path), mode="a", header=False, index=False, lineterminator="\n"
            )
            _append_checkpoint(domain)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def detect_suspected(limit: int = 0) -> None:
    """
    Run bulk gambling content detection on all domains from domains.csv.

    Args:
        limit: If > 0, process only first N domains (dry-run mode).
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
        "detect: %d total | %d already done | %d pending",
        len(all_domains), len(done), len(pending),
    )
    if not pending:
        log.info("Nothing to do - all domains already scanned.")
        return

    csv_path = cfg.SUSPECTED_CSV
    # Write header on fresh run; append-only on resume
    if not done:
        pd.DataFrame(columns=FIELDNAMES).to_csv(
            str(csv_path), index=False, lineterminator="\n"
        )

    semaphore = asyncio.Semaphore(cfg.DETECT_CONCURRENCY)
    lock = asyncio.Lock()

    limits = httpx.Limits(
        max_connections=cfg.DETECT_CONCURRENCY + 20,
        max_keepalive_connections=20,
    )
    async with httpx.AsyncClient(
        timeout=cfg.HTTP_TIMEOUT,
        headers={"User-Agent": cfg.USER_AGENT},
        limits=limits,
        verify=False,
        follow_redirects=True,
    ) as client:
        tasks = [
            _process_domain(client, semaphore, d, csv_path, lock)
            for d in pending
        ]
        pbar = tqdm(total=len(tasks), desc="Detecting", unit="domain", dynamic_ncols=True)
        for coro in asyncio.as_completed(tasks):
            await coro
            pbar.update(1)
        pbar.close()

    # Summary
    df_out = pd.read_csv(csv_path)
    n_suspected = int((df_out["keyword_hits"].fillna(0).astype(int) > 0).sum())
    n_hidden    = int((df_out["hidden_links_found"].fillna(0).astype(int) > 0).sum())
    n_iframes   = int((df_out["iframe_found"].fillna(0).astype(int) > 0).sum())
    log.info(
        "Detection complete: %d/%d domains suspected "
        "(%d keyword | %d hidden-link | %d iframe signals)",
        n_suspected, len(all_domains), n_suspected, n_hidden, n_iframes,
    )
    log.info("Results -> %s", csv_path)

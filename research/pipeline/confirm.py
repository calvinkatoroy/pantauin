"""
Step 3 - Deep Confirmation via Playwright (JS-rendered DOM)

Input:   data/interim/suspected.csv    (rows where keyword_hits > 0
                                        OR hidden_links_found > 0)
Output:  data/processed/confirmed.csv
Resume:  data/checkpoints/confirm.txt  (one domain per line)
Evidence: data/evidence/{domain}_{timestamp}.png  + SHA256 hash

Per suspected domain (async Playwright, concurrency = PLAYWRIGHT_CONCURRENCY):
  1. Fetch raw HTML via httpx (no JS) -> baseline keyword set
  2. Load full page in Chromium (JS-rendered) -> rendered keyword set
  3. Cloaking detection: keywords in rendered-only set = JS-injected gambling content
  4. JS redirect detection: window.location change -> gambling domain
  5. Meta refresh redirect: <meta http-equiv="refresh"> -> gambling domain
  6. Hidden link injection: gambling-signal anchors (expanded from step 2 data)
  7. Take full-page screenshot if any infection signal found
  8. Compute SHA256 of screenshot for chain-of-custody integrity
  9. Compute confidence_score (0-100) from signal count/weight
  10. Set confirmed_infected = True if confidence_score >= 40

Output columns:
  domain, confirmed_infected, confidence_score, cloaking_detected,
  js_redirect, meta_redirect, keyword_count, injected_link_count,
  screenshot_path, screenshot_sha256, page_title, confirmed_at
"""

import asyncio
import hashlib
import logging
import re
import warnings
from pathlib import Path

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from tqdm import tqdm

import research.config as cfg

log = logging.getLogger(__name__)
warnings.filterwarnings("ignore", message=".*SSL.*")

CHECKPOINT_FILE = cfg.DATA_CHECKPOINTS / "confirm.txt"

FIELDNAMES = [
    "domain",
    "confirmed_infected",
    "confidence_score",
    "cloaking_detected",
    "js_redirect",
    "meta_redirect",
    "keyword_count",
    "injected_link_count",
    "screenshot_path",
    "screenshot_sha256",
    "page_title",
    "confirmed_at",
]

_KW_PATTERNS = [
    re.compile(re.escape(kw), re.IGNORECASE) for kw in cfg.GAMBLING_KEYWORDS
]

_GAMBLING_SIGNAL = re.compile(
    r"(slot|judi|togel|casino|betting|poker|gacor|maxwin|sbobet|scatter|toto|zeus|bandar)",
    re.IGNORECASE,
)

# JS to extract all anchor hrefs + texts in one evaluate call
_LINKS_JS = (
    "() => Array.from(document.querySelectorAll('a[href]')).map(a => ({"
    "  href: a.href || '',"
    "  text: (a.textContent || '').trim().slice(0, 200)"
    "}))"
)

# JS to detect window.location assignment redirects in page source
_WL_REDIRECT_RE = re.compile(
    r"window\.location\s*(?:\.href\s*)?=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)

_META_REFRESH_RE = re.compile(r"url\s*=\s*(.+)", re.IGNORECASE)


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

def _match_keywords(text: str) -> set[str]:
    """
    Return set of GAMBLING_KEYWORDS that appear in text.

    Args:
        text: Plaintext or HTML string.

    Returns:
        Set of matched keyword strings.
    """
    return {
        cfg.GAMBLING_KEYWORDS[i]
        for i, pat in enumerate(_KW_PATTERNS)
        if pat.search(text)
    }


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def _compute_confidence(
    keyword_count: int,
    injected_link_count: int,
    js_redirect: bool,
    meta_redirect: bool,
    cloaking_detected: bool,
) -> int:
    """
    Compute an infection confidence score from 0 to 100.

    Scoring rationale:
      - Keywords in rendered DOM: strongest signal (content injection confirmed)
      - Cloaking: high signal (attacker hides content from non-browser scrapers)
      - JS redirect: high signal (browser hijacking)
      - Meta refresh: moderate signal (passive redirect)
      - Injected gambling links: moderate signal

    Args:
        keyword_count:       Number of gambling keywords in rendered DOM.
        injected_link_count: Count of gambling-signal anchor tags.
        js_redirect:         True if page redirected to a gambling domain.
        meta_redirect:       True if meta http-equiv=refresh points to gambling domain.
        cloaking_detected:   True if keywords appear in rendered but not raw HTML.

    Returns:
        Integer score in [0, 100].
    """
    score = 0
    if keyword_count >= 10:
        score += 50
    elif keyword_count >= 5:
        score += 40
    elif keyword_count > 0:
        score += 30
    if cloaking_detected:
        score += 20
    if js_redirect:
        score += 25
    if meta_redirect:
        score += 20
    if injected_link_count >= 5:
        score += 15
    elif injected_link_count > 0:
        score += 10
    return min(score, 100)


# ---------------------------------------------------------------------------
# Raw HTML fetch (httpx, no JS) for cloaking baseline
# ---------------------------------------------------------------------------

async def _fetch_raw_html(domain: str) -> str:
    """
    Fetch raw HTML without executing JavaScript.  Used as baseline for
    cloaking detection (compare against Playwright-rendered DOM).

    Args:
        domain: Domain to fetch.

    Returns:
        Raw HTML string, or empty string on failure.
    """
    for scheme in ("https", "http"):
        try:
            async with httpx.AsyncClient(
                timeout=cfg.HTTP_TIMEOUT,
                headers={"User-Agent": cfg.USER_AGENT},
                verify=False,
                follow_redirects=True,
            ) as client:
                resp = await client.get(f"{scheme}://{domain}")
                if resp.status_code == 200:
                    ct = resp.headers.get("content-type", "")
                    if "text" in ct or "html" in ct:
                        return resp.text
        except Exception:
            continue
    return ""


# ---------------------------------------------------------------------------
# Screenshot + hash
# ---------------------------------------------------------------------------

async def _take_screenshot(page, domain: str) -> tuple[str, str]:
    """
    Take a full-page screenshot and compute its SHA256 hash.

    Args:
        page:   Playwright page object.
        domain: Domain name (used for filename).

    Returns:
        Tuple of (screenshot_path_str, sha256_hex).
        Both are empty strings on failure.
    """
    try:
        from datetime import datetime
        ts = datetime.now(cfg.WIB).strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r"[^\w.-]", "_", domain)[:60]
        fname = f"{slug}_{ts}.png"
        spath = cfg.DATA_EVIDENCE / fname

        await page.screenshot(path=str(spath), full_page=True)

        sha256 = hashlib.sha256(spath.read_bytes()).hexdigest()
        return str(spath), sha256
    except Exception as exc:
        log.debug("Screenshot failed for %s: %s", domain, exc)
        return "", ""


# ---------------------------------------------------------------------------
# Per-domain Playwright worker
# ---------------------------------------------------------------------------

async def _confirm_domain(
    browser,
    semaphore: asyncio.Semaphore,
    domain: str,
    csv_path: Path,
    lock: asyncio.Lock,
) -> None:
    """
    Deep-confirm one suspected domain using Playwright + cloaking check.

    Args:
        browser:  Shared Playwright Browser instance.
        semaphore: Concurrency limiter.
        domain:   Domain to confirm.
        csv_path: Path to confirmed.csv for appending.
        lock:     Asyncio lock protecting CSV writes.
    """
    async with semaphore:
        row = {
            "domain":            domain,
            "confirmed_infected": False,
            "confidence_score":  0,
            "cloaking_detected": False,
            "js_redirect":       False,
            "meta_redirect":     False,
            "keyword_count":     0,
            "injected_link_count": 0,
            "screenshot_path":   "",
            "screenshot_sha256": "",
            "page_title":        "",
            "confirmed_at":      cfg.now_wib(),
        }

        # --- Baseline: raw HTML keywords (no JS) ---
        raw_html = await _fetch_raw_html(domain)
        raw_kw_set = _match_keywords(raw_html) if raw_html else set()

        # --- Check meta refresh in raw HTML ---
        if raw_html:
            soup_raw = BeautifulSoup(raw_html, "lxml")
            meta_refs = soup_raw.find_all(
                "meta", attrs={"http-equiv": re.compile(r"refresh", re.I)}
            )
            for m in meta_refs:
                content = m.get("content", "")
                url_match = _META_REFRESH_RE.search(content)
                if url_match and _GAMBLING_SIGNAL.search(url_match.group(1)):
                    row["meta_redirect"] = True
                    break

        # --- Playwright: JS-rendered DOM ---
        ctx = None
        try:
            ctx = await browser.new_context(
                ignore_https_errors=True,
                user_agent=cfg.USER_AGENT,
            )
            page = await ctx.new_page()

            try:
                await page.goto(
                    f"https://{domain}",
                    wait_until="domcontentloaded",
                    timeout=cfg.PLAYWRIGHT_TIMEOUT,
                )

                final_url = page.url
                row["page_title"] = (await page.title()) or ""

                # JS redirect detection
                if _GAMBLING_SIGNAL.search(final_url):
                    row["js_redirect"] = True

                # Check window.location in raw HTML as secondary JS redirect signal
                if not row["js_redirect"] and raw_html:
                    for wl_match in _WL_REDIRECT_RE.finditer(raw_html):
                        if _GAMBLING_SIGNAL.search(wl_match.group(1)):
                            row["js_redirect"] = True
                            break

                # Rendered text -> keyword set
                try:
                    rendered_text = await page.evaluate(
                        "document.body ? document.body.innerText : ''"
                    )
                    rendered_kw_set = _match_keywords(rendered_text)
                except Exception:
                    rendered_kw_set = set()

                row["keyword_count"] = len(rendered_kw_set)

                # Cloaking: keywords appear in rendered DOM but NOT in raw HTML
                cloaking_signals = rendered_kw_set - raw_kw_set
                row["cloaking_detected"] = bool(cloaking_signals)
                if cloaking_signals:
                    log.debug("Cloaking on %s: JS-only kw = %s", domain, cloaking_signals)

                # Injected gambling links
                try:
                    links = await page.evaluate(_LINKS_JS)
                    row["injected_link_count"] = sum(
                        1 for lnk in links
                        if _GAMBLING_SIGNAL.search(lnk.get("href", ""))
                        or _GAMBLING_SIGNAL.search(lnk.get("text", ""))
                    )
                except Exception:
                    pass

                # Confidence + infection decision
                row["confidence_score"] = _compute_confidence(
                    row["keyword_count"],
                    row["injected_link_count"],
                    row["js_redirect"],
                    row["meta_redirect"],
                    row["cloaking_detected"],
                )
                row["confirmed_infected"] = row["confidence_score"] >= 40

                # Screenshot if any infection signal
                if row["confirmed_infected"] or row["cloaking_detected"] or row["meta_redirect"]:
                    row["screenshot_path"], row["screenshot_sha256"] = (
                        await _take_screenshot(page, domain)
                    )

            except Exception as exc:
                log.debug("Playwright navigation error for %s: %s", domain, exc)
            finally:
                await page.close()

        except Exception as exc:
            log.debug("Playwright context error for %s: %s", domain, exc)
        finally:
            if ctx:
                await ctx.close()

        async with lock:
            pd.DataFrame([row]).to_csv(
                str(csv_path), mode="a", header=False, index=False, lineterminator="\n"
            )
            _append_checkpoint(domain)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def confirm_domains(limit: int = 0) -> None:
    """
    Deep-confirm all suspected domains (keyword_hits > 0 or hidden_links_found > 0).

    Args:
        limit: If > 0, process only first N suspected domains.
    """
    if not cfg.SUSPECTED_CSV.exists():
        raise FileNotFoundError(
            f"{cfg.SUSPECTED_CSV} not found - run `detect` first."
        )

    df_sus = pd.read_csv(cfg.SUSPECTED_CSV, dtype=str)
    suspected = df_sus[
        (df_sus["keyword_hits"].fillna("0").astype(int) > 0)
        | (df_sus["hidden_links_found"].fillna("0").astype(int) > 0)
    ]["domain"].dropna().tolist()

    if limit:
        suspected = suspected[:limit]

    done = _load_checkpoint()
    pending = [d for d in suspected if d not in done]

    log.info(
        "confirm: %d suspected | %d already done | %d pending",
        len(suspected), len(done), len(pending),
    )
    if not pending:
        log.info("Nothing to do - all suspected domains already confirmed.")
        return

    csv_path = cfg.CONFIRMED_CSV
    if not done:
        pd.DataFrame(columns=FIELDNAMES).to_csv(
            str(csv_path), index=False, lineterminator="\n"
        )

    semaphore = asyncio.Semaphore(cfg.PLAYWRIGHT_CONCURRENCY)
    lock = asyncio.Lock()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        tasks = [
            _confirm_domain(browser, semaphore, d, csv_path, lock)
            for d in pending
        ]
        pbar = tqdm(total=len(tasks), desc="Confirming", unit="domain", dynamic_ncols=True)
        for coro in asyncio.as_completed(tasks):
            await coro
            pbar.update(1)
        pbar.close()
        await browser.close()

    df_out = pd.read_csv(csv_path)
    n_confirmed = int(
        (df_out["confirmed_infected"].astype(str).str.lower() == "true").sum()
    )
    n_cloaking = int(
        (df_out["cloaking_detected"].astype(str).str.lower() == "true").sum()
    )
    log.info(
        "Confirmation complete: %d confirmed positive / %d cloaking detected (of %d suspected)",
        n_confirmed, n_cloaking, len(suspected),
    )
    log.info("Results -> %s", csv_path)
    log.info("Evidence -> %s", cfg.DATA_EVIDENCE)

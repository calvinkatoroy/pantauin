"""
Module: page_crawl
Active Playwright crawl - loads page, runs keyword matching, takes screenshot,
detects injected <a> tags and JS/meta redirects.

Contract return shape:
{
    "module": "page_crawl",
    "status": "success" | "error",
    "findings": [...] | None,
    "error": "..." | None,
}
"""
import hashlib
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, quote

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from app.core.config import settings
from app.scanner.keywords import GAMBLING_KEYWORDS, INJECTED_ANCHOR_PATTERNS, GAMBLING_DOMAIN_PATTERNS

# Active keyword list - replaced at scan time with DB-loaded keywords
_ACTIVE_KEYWORDS: list[str] = GAMBLING_KEYWORDS

logger = logging.getLogger(__name__)

# WIB = UTC+7
WIB = timezone(timedelta(hours=7))


def _url_slug(url: str) -> str:
    parsed = urlparse(url)
    slug = (parsed.netloc + parsed.path).replace("/", "_").strip("_")
    return slug[:60] if slug else "page"


def _detect_keywords(text: str) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in _ACTIVE_KEYWORDS if kw.lower() in text_lower]


def _detect_injected_links(page_content: str) -> list[dict]:
    """Find <a> tags with gambling keywords that may be hidden."""
    injected = []
    # Match anchor tags with their text and href
    anchor_re = re.compile(
        r'<a\b([^>]*)>(.*?)</a>',
        re.IGNORECASE | re.DOTALL
    )
    style_hidden_re = re.compile(r'display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0', re.IGNORECASE)

    for match in anchor_re.finditer(page_content):
        attrs, text = match.group(1), match.group(2)
        text_clean = re.sub(r'<[^>]+>', '', text).strip().lower()

        is_hidden = bool(style_hidden_re.search(attrs))
        has_gambling = any(pat in text_clean for pat in INJECTED_ANCHOR_PATTERNS)

        if has_gambling:
            href_match = re.search(r'href=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            injected.append({
                "text": text_clean[:200],
                "href": href_match.group(1) if href_match else "",
                "hidden": is_hidden,
            })

    return injected[:20]  # cap at 20 samples


def _detect_redirect(page_content: str) -> str | None:
    """Detect <meta> or JS redirect to gambling domain."""
    gambling_pattern = "|".join(GAMBLING_DOMAIN_PATTERNS)
    # meta refresh
    meta_re = re.compile(
        r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\'][^"\']*url=([^"\']+)["\']',
        re.IGNORECASE,
    )
    for m in meta_re.finditer(page_content):
        url = m.group(1)
        if re.search(gambling_pattern, url, re.IGNORECASE):
            return url

    # JS window.location
    js_re = re.compile(
        r'window\.location(?:\.href)?\s*=\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )
    for m in js_re.finditer(page_content):
        url = m.group(1)
        if re.search(gambling_pattern, url, re.IGNORECASE):
            return url

    return None


async def crawl_url(url: str, scan_id: str) -> dict | None:
    """Crawl a single URL. Returns a finding dict or None if no gambling found."""
    evidence_dir = os.path.join(settings.evidence_dir, scan_id)
    os.makedirs(evidence_dir, exist_ok=True)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (compatible; PantauInd/1.0; +https://pantauind.id)",
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
            except PlaywrightTimeout:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)

            final_url = page.url
            content = await page.content()
            text_content = await page.evaluate("() => document.body ? document.body.innerText : ''")

            keywords_found = _detect_keywords(text_content)
            injected_links = _detect_injected_links(content)
            redirect_url = _detect_redirect(content)

            if not keywords_found and not injected_links and not redirect_url:
                await browser.close()
                return None

            # Take screenshot
            ts = datetime.now(WIB).strftime("%Y%m%dT%H%M%S")
            slug = _url_slug(url)
            screenshot_name = f"{scan_id}_page_crawl_{slug}_{ts}.png"
            screenshot_path = os.path.join(evidence_dir, screenshot_name)
            await page.screenshot(path=screenshot_path, full_page=True)
            await browser.close()

            # SHA256 hash
            with open(screenshot_path, "rb") as f:
                screenshot_hash = hashlib.sha256(f.read()).hexdigest()

            # Determine severity
            hidden_links = [l for l in injected_links if l.get("hidden")]
            if keywords_found:
                severity = "critical"
            elif hidden_links:
                severity = "high"
            elif injected_links:
                severity = "medium"
            elif redirect_url:
                severity = "high"
            else:
                severity = "medium"

            title_parts = []
            if keywords_found:
                title_parts.append(f"Gambling keywords detected: {', '.join(keywords_found[:3])}")
            if hidden_links:
                title_parts.append(f"{len(hidden_links)} hidden gambling link(s)")
            if redirect_url:
                title_parts.append(f"Redirect to gambling domain")

            return {
                "module": "page_crawl",
                "severity": severity,
                "url": final_url,
                "title": " | ".join(title_parts) or "Gambling content detected",
                "description": (
                    f"Gambling injection detected on {url}. "
                    f"Keywords: {', '.join(keywords_found[:5])}. "
                    f"Injected links: {len(injected_links)}."
                ),
                "evidence_text": text_content[:2000] if text_content else None,
                "screenshot_path": f"{scan_id}/{screenshot_name}",
                "screenshot_hash": screenshot_hash,
                "detected_keywords": keywords_found,
                "injected_links": [l["href"] for l in injected_links if l.get("href")][:10],
            }

    except Exception as e:
        logger.error("page_crawl error for %s: %s", url, e)
        return None


async def run(
    domain: str,
    scan_id: str,
    dork_urls: list[str] | None = None,
    active_keywords: list[str] | None = None,
) -> dict:
    """
    Crawl the domain's root page + any URLs from dork_sweep.
    Accepts active_keywords from DB (seed + auto-discovered) for dynamic matching.
    Returns scraper contract dict.
    """
    # Override module-level keyword list with live DB keywords if provided
    if active_keywords:
        import app.scanner.page_crawl as _self
        _self._ACTIVE_KEYWORDS = active_keywords
    urls_to_crawl: list[str] = []

    # Always crawl root domain
    for scheme in ("https", "http"):
        root = f"{scheme}://{domain}"
        if root not in urls_to_crawl:
            urls_to_crawl.append(root)
            break

    # Add dork hits
    if dork_urls:
        for u in dork_urls:
            if u not in urls_to_crawl:
                urls_to_crawl.append(u)

    findings = []
    for url in urls_to_crawl:
        result = await crawl_url(url, scan_id)
        if result:
            findings.append(result)

    return {
        "module": "page_crawl",
        "status": "success",
        "findings": findings,
        "error": None,
    }

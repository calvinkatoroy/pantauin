"""
Step 1 - Domain Enumeration via Multi-Source Certificate Transparency + Subfinder Fallback

CT sources (run in parallel, results unioned):
  - crt.sh JSON API        (primary)
  - CertSpotter v1 API     (works keyless at 100 req/hr, higher with CERTSPOTTER_API_KEY)
  - Censys v2 certs search (requires CENSYS_API_ID + CENSYS_API_SECRET)

Fallback:
  - Subfinder CLI (ProjectDiscovery) - invoked only if all CT sources return
    zero domains. Requires subfinder binary on PATH.

Output:   data/raw/domains.csv
Columns:  domain, tld, source, discovered_at
          source is pipe-delimited when multiple sources agree:
          "crtsh|certspotter" means both found that domain.

Sources missing credentials or binaries are skipped with a single warning
line; enumeration does not fail as long as at least one source returns data.

Checkpoint: if domains.csv already exists and --force is not set, load from
file instead of re-querying.
"""

import asyncio
import base64
import json
import logging
import re
import shutil
import subprocess
from datetime import timezone

import httpx
import pandas as pd
from tqdm import tqdm

import research.config as cfg

log = logging.getLogger(__name__)

_WILDCARD_RE  = re.compile(r"^\*\.")
_IP_RE        = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
_VALID_FQDN   = re.compile(r"^[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?)*$")

FIELDNAMES = ["domain", "tld", "source", "discovered_at"]


# ---------------------------------------------------------------------------
# Domain helpers
# ---------------------------------------------------------------------------

def _clean_name(raw: str) -> str | None:
    """
    Normalise a raw crt.sh name_value entry.

    Args:
        raw: Raw string from crt.sh name_value field.

    Returns:
        Cleaned FQDN string, or None if it should be discarded.
    """
    name = raw.strip().lower()
    name = _WILDCARD_RE.sub("", name)
    name = name.rstrip(".")

    if not name:
        return None
    if _IP_RE.match(name):   # skip IP literals in certs
        return None
    if not _VALID_FQDN.match(name):
        return None
    return name


def _registered_domain(fqdn: str, tld: str) -> str | None:
    """
    Collapse an FQDN to its registered domain under the given TLD.

    For go.id (2-part TLD):  apps.bkn.go.id  ->  bkn.go.id
    For ac.id (2-part TLD):  cs.ui.ac.id     ->  ui.ac.id

    Args:
        fqdn: Fully-qualified domain name (already cleaned + lowercased).
        tld:  TLD string without leading dot, e.g. "go.id".

    Returns:
        Registered domain string, or None if the FQDN does not belong to this TLD.
    """
    suffix = f".{tld}"
    if not fqdn.endswith(suffix):
        return None

    tld_labels = len(tld.split("."))          # go.id -> 2
    parts = fqdn.split(".")
    # Need at least one label before the TLD
    if len(parts) <= tld_labels:
        return None

    # Take the label immediately before the TLD + the TLD itself
    return ".".join(parts[-(tld_labels + 1):])


def _load_existing(path) -> dict[str, dict]:
    """
    Load already-discovered domains from an existing CSV.

    Returns:
        dict mapping domain -> row dict, or empty dict if file absent.
    """
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path, dtype=str)
        return {row["domain"]: row.to_dict() for _, row in df.iterrows()}
    except Exception as exc:
        log.warning("Could not read existing %s: %s  (will overwrite)", path, exc)
        return {}


# ---------------------------------------------------------------------------
# crt.sh fetch
# ---------------------------------------------------------------------------

_CRTSH_MAX_RETRIES = 6
_CRTSH_BACKOFF_BASE = 5.0   # seconds; 5, 10, 20, 40, 80, 160 -> up to ~5min total


async def _fetch_crtsh(tld: str) -> list[dict]:
    """
    Fetch crt.sh JSON for a single TLD, retrying on transient 5xx errors.

    crt.sh regularly returns 502/503/504 under load; a single failed request
    should not kill enumeration. Retries with exponential backoff.

    Args:
        tld: TLD string without leading dot, e.g. "go.id".

    Returns:
        List of raw entry dicts from crt.sh (empty only if all retries failed).
    """
    url = cfg.CRTSH_URLS.get(tld)
    if not url:
        log.error("No crt.sh URL configured for TLD: %s", tld)
        return []

    log.info("Querying crt.sh for *.%s ...", tld)
    for attempt in range(1, _CRTSH_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            entries = resp.json()
            log.info("  crt.sh returned %d certificate entries for %s", len(entries), tld)
            return entries
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            # 4xx is not worth retrying (bad query, rate limit handled separately)
            if status < 500 and status != 429:
                log.error("crt.sh HTTP %s for %s (not retrying)", status, tld)
                return []
            if attempt == _CRTSH_MAX_RETRIES:
                log.error("crt.sh HTTP %s for %s after %d attempts", status, tld, attempt)
                return []
            delay = _CRTSH_BACKOFF_BASE * (2 ** (attempt - 1))
            log.warning(
                "crt.sh HTTP %s for %s (attempt %d/%d); retrying in %.0fs",
                status, tld, attempt, _CRTSH_MAX_RETRIES, delay,
            )
            await asyncio.sleep(delay)
        except (httpx.TransportError, httpx.ReadTimeout) as exc:
            if attempt == _CRTSH_MAX_RETRIES:
                log.error("crt.sh transport error for %s after %d attempts: %s", tld, attempt, exc)
                return []
            delay = _CRTSH_BACKOFF_BASE * (2 ** (attempt - 1))
            log.warning(
                "crt.sh transport error for %s: %s (attempt %d/%d); retrying in %.0fs",
                tld, exc, attempt, _CRTSH_MAX_RETRIES, delay,
            )
            await asyncio.sleep(delay)
        except Exception as exc:
            log.error("crt.sh fetch failed for %s: %s", tld, exc)
            return []
    return []


# ---------------------------------------------------------------------------
# CertSpotter fetch
# ---------------------------------------------------------------------------

async def _fetch_certspotter(tld: str) -> set[str]:
    """
    Fetch registered domains under `tld` from CertSpotter (SSLMate).

    Uses v1 issuances endpoint with pagination via ?after=<id>. Free tier
    is 100 req/hour keyless; higher with CERTSPOTTER_API_KEY.

    Args:
        tld: TLD string without leading dot, e.g. "go.id".

    Returns:
        Set of registered domain strings under `tld` (may be empty on failure).
    """
    found: set[str] = set()
    headers = {"Accept": "application/json"}
    if cfg.CERTSPOTTER_API_KEY:
        headers["Authorization"] = f"Bearer {cfg.CERTSPOTTER_API_KEY}"

    params = {
        "domain": tld,
        "include_subdomains": "true",
        "match_wildcards": "true",
        "expand": "dns_names",
    }

    log.info("Querying CertSpotter for *.%s ...", tld)
    after: str | None = None
    pages = 0
    try:
        async with httpx.AsyncClient(timeout=60.0, headers=headers) as client:
            while True:
                q = dict(params)
                if after:
                    q["after"] = after
                resp = await client.get(cfg.CERTSPOTTER_URL, params=q)
                if resp.status_code == 429:
                    log.warning("CertSpotter rate-limited; stopping at %d pages", pages)
                    break
                if resp.status_code >= 400:
                    log.warning("CertSpotter HTTP %s (stopping)", resp.status_code)
                    break
                entries = resp.json()
                if not entries:
                    break
                pages += 1
                for entry in entries:
                    for raw in entry.get("dns_names", []) or []:
                        name = _clean_name(raw)
                        if not name:
                            continue
                        reg = _registered_domain(name, tld)
                        if reg:
                            found.add(reg)
                    # Track latest id for pagination cursor
                    if "id" in entry:
                        after = str(entry["id"])
                # CertSpotter returns up to 256 per page; stop if under
                if len(entries) < 256:
                    break
    except Exception as exc:
        log.warning("CertSpotter fetch failed for %s: %s", tld, exc)

    log.info("  CertSpotter: %d unique registered domains (%d pages)", len(found), pages)
    return found


# ---------------------------------------------------------------------------
# Censys fetch
# ---------------------------------------------------------------------------

async def _fetch_censys(tld: str) -> set[str]:
    """
    Fetch registered domains under `tld` from Censys v2 certificates search.

    Requires CENSYS_API_ID + CENSYS_API_SECRET. Free tier: 250 queries/month.
    Uses cursor-based pagination, bounded at 50 pages to stay inside quota.

    Args:
        tld: TLD string without leading dot, e.g. "go.id".

    Returns:
        Set of registered domain strings under `tld` (may be empty on failure).
    """
    if not (cfg.CENSYS_API_ID and cfg.CENSYS_API_SECRET):
        log.info("Censys: skipped (CENSYS_API_ID / CENSYS_API_SECRET not set)")
        return set()

    found: set[str] = set()
    token = base64.b64encode(
        f"{cfg.CENSYS_API_ID}:{cfg.CENSYS_API_SECRET}".encode()
    ).decode()
    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    log.info("Querying Censys for *.%s ...", tld)
    cursor: str | None = None
    pages = 0
    max_pages = 50  # soft cap to protect monthly quota
    try:
        async with httpx.AsyncClient(timeout=60.0, headers=headers) as client:
            while pages < max_pages:
                body: dict = {"q": f"names: *.{tld}", "per_page": 100}
                if cursor:
                    body["cursor"] = cursor
                resp = await client.post(cfg.CENSYS_SEARCH_URL, content=json.dumps(body))
                if resp.status_code == 429:
                    log.warning("Censys rate-limited; stopping at %d pages", pages)
                    break
                if resp.status_code >= 400:
                    log.warning("Censys HTTP %s: %s", resp.status_code, resp.text[:200])
                    break
                data = resp.json()
                result = data.get("result", {})
                hits = result.get("hits", []) or []
                if not hits:
                    break
                pages += 1
                for hit in hits:
                    names = hit.get("names", []) or []
                    for raw in names:
                        name = _clean_name(raw)
                        if not name:
                            continue
                        reg = _registered_domain(name, tld)
                        if reg:
                            found.add(reg)
                cursor = result.get("links", {}).get("next") or None
                if not cursor:
                    break
    except Exception as exc:
        log.warning("Censys fetch failed for %s: %s", tld, exc)

    log.info("  Censys: %d unique registered domains (%d pages)", len(found), pages)
    return found


# ---------------------------------------------------------------------------
# Subfinder fallback (CLI subprocess)
# ---------------------------------------------------------------------------

def _fetch_subfinder(tld: str) -> set[str]:
    """
    Invoke Subfinder CLI to enumerate domains under `tld`.

    Subfinder aggregates ~30 passive sources (CT logs, passive DNS, search
    engines). Runs as a subprocess since it's a Go binary.

    Args:
        tld: TLD string without leading dot, e.g. "go.id".

    Returns:
        Set of registered domain strings under `tld` (empty if binary missing).
    """
    if not shutil.which(cfg.SUBFINDER_BIN):
        log.warning(
            "Subfinder: binary '%s' not on PATH - fallback unavailable. "
            "Install from https://github.com/projectdiscovery/subfinder",
            cfg.SUBFINDER_BIN,
        )
        return set()

    log.info("Running Subfinder fallback for *.%s ...", tld)
    found: set[str] = set()
    try:
        proc = subprocess.run(
            [cfg.SUBFINDER_BIN, "-d", tld, "-all", "-silent"],
            capture_output=True,
            text=True,
            timeout=cfg.SUBFINDER_TIMEOUT,
            check=False,
        )
        if proc.returncode != 0:
            log.warning("Subfinder exited %d: %s", proc.returncode, proc.stderr[:300])
        for line in proc.stdout.splitlines():
            name = _clean_name(line)
            if not name:
                continue
            reg = _registered_domain(name, tld)
            if reg:
                found.add(reg)
    except subprocess.TimeoutExpired:
        log.warning("Subfinder timed out after %ds for %s", cfg.SUBFINDER_TIMEOUT, tld)
    except Exception as exc:
        log.warning("Subfinder failed for %s: %s", tld, exc)

    log.info("  Subfinder: %d unique registered domains", len(found))
    return found


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def enumerate_domains(limit: int = 0, force: bool = False) -> list[str]:
    """
    Enumerate .go.id and .ac.id registered domains via crt.sh CT logs.

    Args:
        limit: If > 0, truncate output to first N domains (dry-run mode).
        force: If True, re-fetch from crt.sh even if domains.csv exists.

    Returns:
        Sorted list of unique registered domain strings.
    """
    # Resume: load from existing file unless forced
    existing = _load_existing(cfg.DOMAINS_CSV)
    if existing and not force:
        log.info(
            "domains.csv already has %d domains. Use --force to re-fetch from crt.sh.",
            len(existing),
        )
        domains = sorted(existing.keys())
        if limit:
            domains = domains[:limit]
        return domains

    # Fresh fetch - multi-source per TLD, union results, record all sources.
    discovered: dict[str, dict] = dict(existing)

    for tld in cfg.TARGET_TLDS:
        # ----- Extract crt.sh registered domains into a set like the others -----
        crtsh_entries = await _fetch_crtsh(tld)
        crtsh_set: set[str] = set()
        for entry in crtsh_entries:
            for raw in entry.get("name_value", "").split("\n"):
                name = _clean_name(raw)
                if not name:
                    continue
                reg = _registered_domain(name, tld)
                if reg:
                    crtsh_set.add(reg)
        log.info("  crt.sh: %d unique registered domains", len(crtsh_set))

        # ----- Run CertSpotter + Censys in parallel with crt.sh already done ---
        certspotter_set, censys_set = await asyncio.gather(
            _fetch_certspotter(tld),
            _fetch_censys(tld),
        )

        per_source: dict[str, set[str]] = {
            "crtsh":       crtsh_set,
            "certspotter": certspotter_set,
            "censys":      censys_set,
        }

        # ----- If all CT sources came up empty, fall back to Subfinder --------
        if not any(per_source.values()):
            log.warning(
                "All CT sources returned 0 domains for .%s - invoking Subfinder fallback",
                tld,
            )
            per_source["subfinder"] = _fetch_subfinder(tld)

        # ----- Union and annotate with source provenance ----------------------
        new_for_tld = 0
        for src_name, reg_set in per_source.items():
            for reg in reg_set:
                if reg in discovered:
                    # Append this source to existing provenance string
                    cur = discovered[reg]["source"]
                    if src_name not in cur.split("|"):
                        discovered[reg]["source"] = f"{cur}|{src_name}"
                else:
                    discovered[reg] = {
                        "domain":        reg,
                        "tld":           tld,
                        "source":        src_name,
                        "discovered_at": cfg.now_wib(),
                    }
                    new_for_tld += 1

        log.info(
            "  .%s union: %d unique registered domains (%d new this run)",
            tld, sum(1 for d in discovered.values() if d["tld"] == tld), new_for_tld,
        )

    all_domains = sorted(discovered.keys())
    log.info("Total unique registered domains: %d", len(all_domains))

    if limit:
        log.info("Applying limit: keeping first %d of %d", limit, len(all_domains))
        all_domains = all_domains[:limit]
        discovered = {d: discovered[d] for d in all_domains}

    # Write with pandas
    df = pd.DataFrame(list(discovered.values()), columns=FIELDNAMES)
    df = df.sort_values("domain").reset_index(drop=True)
    df.to_csv(cfg.DOMAINS_CSV, index=False, lineterminator="\n")
    log.info("Saved %d domains -> %s", len(df), cfg.DOMAINS_CSV)

    return all_domains

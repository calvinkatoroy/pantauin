"""
Step 1 - Domain Enumeration via crt.sh Certificate Transparency Logs

Sources:  https://crt.sh/?q=%.go.id&output=json
          https://crt.sh/?q=%.ac.id&output=json
Output:   data/raw/domains.csv
Columns:  domain, tld, source, discovered_at

Algorithm:
  1. Query crt.sh JSON API for each TLD in TARGET_TLDS
  2. Extract name_value field (can contain newline-separated SAN entries)
  3. Strip wildcard prefix (*.domain.go.id -> domain.go.id)
  4. Filter out IP addresses and non-TLD entries
  5. Collapse to registered domain (strip subdomains):
     apps.bkn.go.id -> bkn.go.id
  6. Deduplicate across TLDs
  7. Write to domains.csv with metadata columns

Checkpoint: if domains.csv already exists and --force is not set, load from
file instead of re-querying crt.sh (saves API quota + time on resume).

Runtime: 3-8 minutes for full .go.id + .ac.id namespace (100k+ CT entries).
"""

import logging
import re
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

async def _fetch_crtsh(tld: str) -> list[dict]:
    """
    Fetch crt.sh JSON for a single TLD.

    Args:
        tld: TLD string without leading dot, e.g. "go.id".

    Returns:
        List of raw entry dicts from crt.sh (may be empty on error).
    """
    url = cfg.CRTSH_URLS.get(tld)
    if not url:
        log.error("No crt.sh URL configured for TLD: %s", tld)
        return []

    log.info("Querying crt.sh for *.%s ...", tld)
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        entries = resp.json()
        log.info("  crt.sh returned %d certificate entries for %s", len(entries), tld)
        return entries
    except httpx.HTTPStatusError as exc:
        log.error("crt.sh HTTP %s for %s", exc.response.status_code, tld)
        return []
    except Exception as exc:
        log.error("crt.sh fetch failed for %s: %s", tld, exc)
        return []


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

    # Fresh fetch
    discovered: dict[str, dict] = dict(existing)  # preserve if merging

    for tld in cfg.TARGET_TLDS:
        entries = await _fetch_crtsh(tld)
        if not entries:
            continue

        new_for_tld = 0
        for entry in tqdm(entries, desc=f"Parsing {tld} certs", unit="cert", leave=False):
            for raw in entry.get("name_value", "").split("\n"):
                name = _clean_name(raw)
                if not name:
                    continue
                reg = _registered_domain(name, tld)
                if reg and reg not in discovered:
                    discovered[reg] = {
                        "domain":       reg,
                        "tld":          tld,
                        "source":       "crt.sh",
                        "discovered_at": cfg.now_wib(),
                    }
                    new_for_tld += 1

        log.info("  New unique .%s registered domains: %d", tld, new_for_tld)

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

"""
CVSS-lite scoring for PantauInd findings.

Produces a numeric score 0.0–10.0 per finding based on:
  - Severity label (base score)
  - Module type (contextual adjustment)
  - Evidence factors (screenshot confirmed, keyword density, injected links)

Not a full CVSS implementation - a simplified analog appropriate for
gambling injection + passive vuln surface findings.
"""

# Base scores by severity
_BASE: dict[str, float] = {
    "critical": 9.0,
    "high":     7.0,
    "medium":   5.0,
    "low":      3.0,
    "info":     1.0,
}

# Module-specific overrides applied before evidence modifiers
_MODULE_OVERRIDES: dict[tuple[str, str], float] = {
    # Confirmed gambling injection with Playwright evidence
    ("page_crawl", "critical"): 9.5,
    # Hidden injected links
    ("page_crawl", "high"): 8.0,
    # Dork hit - not yet confirmed by crawl
    ("dork_sweep", "high"): 6.5,
    # Exposed sensitive files (.env, .git, config.php)
    ("path_probe", "high"): 8.5,
    # Exposed admin panels
    ("path_probe", "medium"): 5.5,
    # Server version disclosure
    ("header_probe", "medium"): 4.5,
}


def compute_cvss_lite(
    severity: str,
    module: str,
    detected_keywords: list[str],
    injected_links: list[str],
    has_screenshot: bool,
) -> float:
    """
    Return a CVSS-lite score in [0.0, 10.0] for a single finding.
    """
    score = _MODULE_OVERRIDES.get((module, severity), _BASE.get(severity, 1.0))

    # Evidence modifiers - each capped to avoid runaway inflation
    if has_screenshot:
        score = min(score + 0.3, 10.0)

    if len(detected_keywords) >= 5:
        score = min(score + 0.2, 10.0)
    elif len(detected_keywords) >= 10:
        score = min(score + 0.4, 10.0)

    if len(injected_links) >= 3:
        score = min(score + 0.3, 10.0)

    return round(score, 1)

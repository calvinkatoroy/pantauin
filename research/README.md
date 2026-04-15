# PantauInd Research Pipeline

**Thesis:** *Attack Surface Profiling of Gambling-Injected Indonesian Government Websites Using Passive Web Reconnaissance: A National-Scale Empirical Study*
**Institution:** Universitas Indonesia, Computer Engineering, 2026
**Author:** Calvin Wirathama Katoroy

---

## Research Gap

Prior work (Nurseno et al. 2024, Zagi et al. 2025, Riyadi et al. 2025) detects or classifies gambling SEO injection on .go.id domains but does not correlate infection status with passive attack surface characteristics. This pipeline addresses that gap by:

1. Enumerating the full .go.id / .ac.id namespace via Certificate Transparency logs
2. Detecting gambling injection at scale using lightweight HTTP scanning
3. Confirming positive cases via full JS rendering (Playwright), with cloaking detection
4. Profiling the passive attack surface of ALL domains (infected + clean)
5. Running chi-square + logistic regression to identify which vulnerability features correlate statistically with infection

**Novel contribution:** First national-scale empirical study correlating .go.id gambling injection with passive attack surface metrics.

---

## Pipeline Overview

```
crt.sh CT logs
      |
      v
[1] enumerate.py -----> data/raw/domains.csv
      (registered domain dedup, IP filter, .go.id + .ac.id)
      |
      v
[2] detect.py ----------> data/interim/suspected.csv
      (httpx + BeautifulSoup, concurrency=50, checkpoint/resume)
      (keywords, meta tags, hidden links, iframes, false-positive filter)
      |
      v (keyword_hits > 0 OR hidden_links > 0)
[3] confirm.py ---------> data/processed/confirmed.csv
      (Playwright, concurrency=8, cloaking detection, SHA256 screenshots)
      |
[4] surface.py ---------> data/processed/attack_surface.csv
      (ALL domains from step 1, concurrency=30, checkpoint/resume)
      (headers, SSL, CMS, exposed paths, cookie flags)
      |
      v (merge on domain)
[5] analysis.py --------> data/tables/ + data/figures/
      (chi-square + Bonferroni, logistic regression + VIF, 4 figures)
```

---

## Installation

```bash
# From repo root
pip install -r research/requirements.txt
playwright install chromium
```

**Python 3.11+ required.** Tested on Windows 11 and Ubuntu 22.04.

---

## Usage

### Dry run (50 domains, verify pipeline works end-to-end)

```bash
python -m research.cli --dry-run run-all
```

### Full pipeline

```bash
python -m research.cli run-all
```

### Individual steps (all support checkpoint/resume - safe to kill and restart)

```bash
python -m research.cli enumerate          # Step 1: fetch domain list
python -m research.cli enumerate --force  # Step 1: re-fetch (overwrite)
python -m research.cli detect             # Step 2: bulk detection
python -m research.cli confirm            # Step 3: deep confirmation
python -m research.cli surface            # Step 4: attack surface profiling
python -m research.cli analyse            # Step 5: statistics
```

### Custom output directory

```bash
python -m research.cli --output-dir /mnt/nvme/thesis-data run-all
# Or via env var:
export RESEARCH_DATA_DIR=/mnt/nvme/thesis-data
python -m research.cli run-all
```

---

## Output Files

```
data/
├── raw/
│   └── domains.csv              # domain, tld, source, discovered_at
├── interim/
│   └── suspected.csv            # all scanned domains + keyword_hits, hidden_links_found
├── processed/
│   ├── confirmed.csv            # confirmed_infected, confidence_score, screenshot_sha256
│   └── attack_surface.csv      # all attack surface features per domain
├── evidence/
│   └── {domain}_{timestamp}.png # Playwright screenshots (confirmed infections only)
├── tables/
│   ├── descriptive.{csv,tex}
│   ├── chisquare.{csv,tex}
│   ├── logistic_regression.{csv,tex}
│   └── vif.{csv,tex}
├── figures/
│   ├── feature_prevalence.png   # grouped bar: infected vs clean feature rates
│   ├── odds_ratio_forest.png    # forest plot from logistic regression
│   ├── infection_distribution.png  # infection rate overall + by TLD
│   └── cms_distribution.png    # stacked bar: CMS type vs infection status
└── checkpoints/
    ├── detect.txt               # domains already scanned (step 2)
    ├── confirm.txt              # domains already confirmed (step 3)
    └── surface.txt              # domains already profiled (step 4)
```

### LaTeX integration

Paste tables directly into your thesis:

```latex
\input{data/tables/descriptive.tex}
\input{data/tables/chisquare.tex}
\input{data/tables/logistic_regression.tex}
```

Include figures:

```latex
\includegraphics[width=\textwidth]{data/figures/feature_prevalence.png}
```

---

## Configuration

Edit `research/config.py` to adjust:

| Constant | Default | Description |
|---|---|---|
| `TARGET_TLDS` | `["go.id", "ac.id"]` | TLDs to enumerate |
| `DETECT_CONCURRENCY` | 50 | httpx workers for step 2 |
| `SURFACE_CONCURRENCY` | 30 | httpx workers for step 4 |
| `PLAYWRIGHT_CONCURRENCY` | 8 | Playwright pages for step 3 |
| `HTTP_TIMEOUT` | 10s | Per-request timeout |
| `PLAYWRIGHT_TIMEOUT` | 20s | Per-page navigation timeout |
| `ALPHA` | 0.05 | Chi-square significance level |
| `VIF_THRESHOLD` | 10.0 | Multicollinearity threshold |

---

## Ethical Disclaimer

This pipeline performs **passive reconnaissance only**:

- All HTTP requests are GET-only. No POST, no form submission, no authentication bypass.
- No payload injection of any kind. No XSS, SQLi, command injection, or active CVE testing.
- No Shodan, shodan-like active scanning, or port scanning.
- No credentials are collected, stored, or transmitted.
- SSL verification is disabled only to ensure consistent measurement across sites with expired/self-signed certificates - this is a measurement decision, not an attack.
- Screenshots are stored locally and never uploaded to third-party services.
- The purpose is academic: measuring the security posture of government websites to inform remediation policy.

This research was conducted under the ethical guidelines of Universitas Indonesia's research ethics framework. Findings are reported in aggregate. No individual domain is singled out in the thesis without citing publicly observable evidence.

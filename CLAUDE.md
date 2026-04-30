# CLAUDE.md - PantauInd Research Pipeline

## What This Branch Is

This branch hosts the **research CLI pipeline** for Calvin Wirathama Katoroy's empirical study on gambling SEO injection in Indonesian government domains.

The companion web scanner tool (FastAPI + React) lives on the `web-tool` / `main` branches and is intentionally **not present here**. This branch is CSV-first, no database, no web UI - just a 5-stage CLI for national-scale data collection and statistical analysis.

## Repository Branches

- `main` - stable web tool baseline
- `web-tool` - active web tool development
- `research-pipeline` - this branch (CLI pipeline only)

## Research Title

Attack Surface Profiling of Gambling-Injected Indonesian Government Websites Using Passive Web Reconnaissance: A National-Scale Empirical Study

## Research Questions

- **RQ1:** Prevalence and distribution of gambling SEO injection on `.go.id` at national scale
- **RQ2:** Attack surface characteristics of infected vs. clean domains (security headers, exposed paths, CMS, version disclosure)
- **RQ3:** Statistical correlation between vulnerability features and infection status (chi-square + logistic regression)

## Pipeline

```
enumerate.py  ->  crt.sh + CertSpotter + Censys (parallel) + Subfinder fallback
                                          ->  data/raw/domains.csv
detect.py     ->  httpx + BS4 + tier-weighted keywords
                                          ->  data/interim/suspected.csv
confirm.py    ->  Playwright async (concurrency=8), outerHTML + cloaking detection
                                          ->  data/processed/confirmed.csv
surface.py    ->  httpx GET-only passive recon
                                          ->  data/processed/attack_surface.csv
analysis.py   ->  statsmodels Logit + chi-square + Bonferroni
                                          ->  data/tables/ + data/figures/
```

## Tech Stack

| Layer | Tech |
| --- | --- |
| Enumeration | crt.sh API, CertSpotter API, Censys API, Subfinder (fallback) |
| Detection | httpx async, BeautifulSoup |
| Confirmation | Playwright async (concurrency=8) |
| Profiling | httpx GET-only passive recon |
| Analysis | statsmodels, scipy, pandas, seaborn |
| Environment | Python 3.11+, Google Colab (analysis stage) |

## Absolute Constraints

- **Passive recon ONLY** - GET requests, zero payload injection, no active exploitation
- **No database** - CSV files only (pandas)
- **No web framework** - CLI only, no FastAPI / no Celery / no Redis
- **Python 3.11+** (3.14 verified)
- **Windows compatible** AND Linux portable
- **`data/` is gitignored entirely** - never commit domain lists or scan results
- **No em dashes** - use hyphens in all source code, comments, and documentation
- **No ML for detection** - rule-based tiered keyword matching is deliberate (explainability for evidence)
- **No supervisor mentioned** - this is a personal research project

## Key Design Decisions

- **httpx + BS4 for bulk detection** - speed, no browser overhead for 20-50k domains
- **Playwright only for suspected ~5%** - RAM efficiency on 16GB laptop
- **statsmodels Logit, not sklearn** - thesis needs p-values, 95% CI, interpretable coefficients
- **All domains profiled** (infected + clean) - control group for chi-square and logistic regression
- **Multi-source CT enumeration** - crt.sh + CertSpotter + Censys in parallel, Subfinder fallback only when all CT sources return 0
- **Tier-weighted keyword scoring** - Tier A 15pts/cap 50, Tier B 8pts/cap 30, Tier C 5pts requires >=3 hits
- **outerHTML matching in confirm.py** - catches CSS-hidden injection that innerText misses
- **Two-way cloaking detection** - JS-injected (`cloaking_detected`) and CSS-hidden (`hidden_seo_injection`)
- **CSV for all data** - simple, portable, pandas-native, Colab-friendly

## Statistical Analysis

- Chi-square per feature + Bonferroni correction
- Fisher's exact fallback if expected cell < 5
- Logistic regression: OR, 95% CI, p-value, pseudo-R-squared, AIC
- VIF check for multicollinearity (flag if VIF > 10)
- Hosmer-Lemeshow goodness-of-fit
- Output: CSV + LaTeX tables, PNG 300 DPI figures

## Prior Work to Be Aware Of

**Gambling detection (detection only, no vuln profiling):**
- Nurseno et al. 2024 (MATRIK) - Python scraping, 450k .go.id
- Zagi et al. 2025 (ArXiv) - dork + crawl, 1-month measurement
- Riyadi et al. 2025 (bit-Tech) - RF + SVM classifier
- Teppap et al. 2024 (IEEE JCSSE) - BeautifulSoup detection

**Methodology anchors (vulnerability correlation):**
- Vasek & Moore 2016 (IEEE TDSC) - CMS as compromise risk factor
- Kovacevic et al. 2022 (SoftCOM) - website features predict compromise
- Harry et al. 2025 (J. Cybersecurity) - national-scale US gov attack surface
- Kasturi et al. 2023 (IEEE ITNAC) - vulnerability features as compromise indicators

**Indonesian gov security (no gambling ground truth):**
- Almaarif et al. 2020 (IJASET) - .go.id security headers
- Darojat et al. 2022 (JSIB) - specific .go.id domain assessment
- Suyitno et al. 2024 (ICETIA) - passive vuln assessment of Indonesian gov

## Output Formats

- All data: CSV (pandas)
- All figures: PNG 300 DPI (seaborn/matplotlib)
- All tables: .csv + .tex (paste-ready LaTeX)
- Timestamps: WIB (UTC+7), ISO 8601

## File Structure

```
research/
├── README.md             Pipeline usage docs
├── cli.py                CLI entrypoint (run-all, individual stages, dry-run)
├── config.py             Tier A/B/C keyword lists + regex + thresholds
├── requirements.txt      Pinned Python deps
└── pipeline/
    ├── enumerate.py      Multi-source CT enumeration (crt.sh, CertSpotter, Censys, Subfinder)
    ├── detect.py         Bulk httpx + BS4 keyword scan -> suspected.csv
    ├── confirm.py        Playwright deep verification, tier-weighted scoring, cloaking
    ├── surface.py        Passive vuln surface profiling (headers, paths, CMS)
    └── analysis.py       Chi-square + logistic regression + LaTeX/PNG output
```

## Required Environment Variables

```bash
# CT log enumeration (multi-source, all optional but each adds coverage)
CERTSPOTTER_API_KEY=
CENSYS_API_ID=
CENSYS_API_SECRET=

# Subfinder is invoked as a binary if on PATH; no env var needed
```

If all CT sources are unauthenticated and crt.sh is throttled, the run is coverage-starved. Sign up for at least CertSpotter or Censys before a full namespace run.

## Conventions

- Python: type hints, async where parallelism matters
- Commits: conventional commits (feat:, fix:, chore:, docs:)
- Comments: English only
- No em dashes - use hyphens
- All output paths under `data/` (gitignored)

## Do Not Touch

- `data/` folder - gitignored, never commit
- Statistical methodology - locked for the specific research design (chi-square + logit on RQ3)
- Web tool code - it does not exist on this branch and should not be added here

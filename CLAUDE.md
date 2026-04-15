# CLAUDE.md - PantauInd Context

## What This Project Is

PantauInd is a personal security research project by Calvin Wirathama Katoroy (Computer Engineering, Universitas Indonesia). It serves two purposes:

1. **Web scanner tool** (`main` branch) - FastAPI + React application that detects gambling SEO injection and passive vulnerability surfaces on `.go.id` / `.ac.id` domains
2. **Research CLI pipeline** (`research-pipeline` branch) - 5-stage data collection and statistical analysis instrument for an empirical study

The problem: thousands of Indonesian government websites are compromised with gambling SEO injection. Existing work detects the infection but nobody has empirically studied what vulnerability characteristics make domains susceptible. This project bridges that gap.

## Repository Branches

- `main` - web tool, stable, do not break
- `research-pipeline` - CLI pipeline, active development

## Research Title

Attack Surface Profiling of Gambling-Injected Indonesian Government Websites Using Passive Web Reconnaissance: A National-Scale Empirical Study

## Research Questions

- **RQ1:** Prevalence and distribution of gambling SEO injection on `.go.id` at national scale
- **RQ2:** Attack surface characteristics of infected vs. clean domains (security headers, exposed paths, CMS, version disclosure)
- **RQ3:** Statistical correlation between vulnerability features and infection status (chi-square + logistic regression)

## Pipeline (research-pipeline branch)

```
enumerate.py  ->  crt.sh / Subfinder  ->  data/raw/domains.csv
detect.py     ->  httpx + BS4         ->  data/interim/suspected.csv
confirm.py    ->  Playwright          ->  data/processed/confirmed.csv
surface.py    ->  httpx passive       ->  data/processed/attack_surface.csv
analysis.py   ->  statsmodels         ->  data/tables/ + data/figures/
```

## Web Tool Architecture (main branch)

```
React Frontend (Vite + Tailwind, dark theme)
    polls GET /api/scan/{id} every 2s
    AuthGate -> login/setup form, X-API-Key in localStorage

FastAPI Backend (async, Pydantic v2)
    Auth: multi-user RBAC or legacy single API_KEY
    Rate limited: 10/min scan, 3/min bulk (slowapi)
    Redis cache: terminal scans cached 300s

Celery Worker (concurrency=4)
    scan_tasks.run_scan - single domain pipeline
    tld_sweep_tasks.run_tld_sweep - namespace sweep + child dispatch

Scan Pipeline (scanner/pipeline.py - module registry):
    dork_sweep -> page_crawl -> header_probe -> path_probe ->
    cms_detect -> shodan_probe (optional) -> subdomain_enum

Infrastructure (docker-compose):
    PostgreSQL 16, Redis 7, Celery worker, Celery beat (single instance)
```

## Tech Stack

### Web Tool (main)

| Layer | Tech |
| --- | --- |
| Frontend | React 18 + Tailwind CSS (Vite), dark theme |
| Backend | FastAPI (Python 3.11+), async, Pydantic v2 |
| Scraping | Playwright (async) - screenshots + JS rendering |
| HTTP probing | httpx |
| Search | Serper.dev API (Google-backed dork queries) |
| Database | SQLite (dev) / PostgreSQL (prod, asyncpg) |
| Migrations | Alembic |
| PDF Export | WeasyPrint |
| Task Queue | Celery + Redis |
| Caching | Redis (300s TTL for completed scans) |
| Auth | Multi-user RBAC (X-API-Key header) |
| Deployment | Docker Compose / Fly.io (sin region) |
| CI/CD | GitHub Actions |

### Research Pipeline (research-pipeline)

| Layer | Tech |
| --- | --- |
| Enumeration | crt.sh API, Subfinder |
| Detection | httpx async, BeautifulSoup |
| Confirmation | Playwright async (concurrency=8) |
| Profiling | httpx GET-only passive recon |
| Analysis | statsmodels, scipy, pandas, seaborn |
| Environment | Google Colab (analysis stage) |

## Absolute Constraints

- **Passive recon ONLY** - GET requests, zero payload injection, no active exploitation
- **No database for research pipeline** - CSV files only (pandas)
- **Python 3.11+**
- **Windows compatible** (d:/pantauin) AND Linux portable
- **data/ is gitignored entirely** - never commit domain lists or scan results
- **No em dashes** - use hyphens in all source code, comments, and documentation
- **No ML for detection** - rule-based keyword matching is deliberate (explainability for evidence)
- **Scraper contract** - every scanner module returns: `{"module": "<name>", "status": "success"|"error"|"skipped", "findings": [...]|null, "error": "..."|null}`
- **Module registry** - adding a scanner = create file + add PipelineModule to PIPELINE list
- **Shodan is conditional** - only active when SHODAN_API_KEY is set, no ghost ModuleStatus rows
- **Celery beat: single instance** - never scale > 1
- **No supervisor mentioned** - this is a personal project

## Key Design Decisions (Web Tool)

- **Evidence storage abstracted** via core/storage.py (local disk or S3/R2)
- **TLD sweep auto-detection** - input starting with `.` triggers namespace sweep
- **Celery tasks are sync** calling `asyncio.run()` on async implementation
- **SQLite for dev, PostgreSQL for prod** - docker-compose injects DATABASE_URL
- **Pydantic v2** - use model_validator, field_validator (not v1 syntax)
- **Dark UI** - bg #0a0c0f, surface #111318, border #2a2d35, accent #e8c547
- **CVSS-lite scores** computed per finding in _save_findings via scoring.compute_cvss_lite()
- **Auth** - multi-user RBAC, backward-compat with legacy single API_KEY
- **Redis cache invalidation** - lifecycle PATCH must delete parent scan's cache key
- **Scan diff fingerprinting** - dork_sweep uses (module, url); others use (module, url, title)
- **Finding lifecycle is analyst-controlled** - diff engine sets delta_tag but never changes lifecycle_status

## Key Design Decisions (Research Pipeline)

- **httpx + BS4 for bulk detection** - speed, no browser overhead for 20-50k domains
- **Playwright only for suspected ~5%** - RAM efficiency on 16GB laptop
- **statsmodels Logit, not sklearn** - thesis needs p-values, 95% CI, interpretable coefficients
- **All domains profiled** (infected + clean) - control group for chi-square and logistic regression
- **crt.sh + Subfinder** - free, no rate limits, comprehensive CT log coverage
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

## API Endpoints (Web Tool)

| Method | Path | Description |
| --- | --- | --- |
| POST | /api/scan | Start scan (single domain or TLD sweep). Rate: 10/min |
| DELETE | /api/scan/{id} | Cancel scan (revokes Celery task) |
| GET | /api/scan/{id} | Poll status + findings + modules + children + delta |
| GET | /api/scans | Scan history (paginated, filterable) |
| GET | /api/trend | Domain trend (per-scan finding counts) |
| POST | /api/scan/bulk | CSV upload, dispatches per domain. Rate: 3/min |
| GET | /api/scan/{id}/report | HTML report download |
| GET | /api/scan/{id}/report/pdf | PDF report download |
| PATCH | /api/finding/{id}/lifecycle | Update finding lifecycle status |
| POST | /api/schedules | Create recurring scan schedule |
| GET | /api/schedules | List schedules |
| PATCH | /api/schedules/{id} | Update schedule |
| DELETE | /api/schedules/{id} | Delete schedule |
| GET | /api/keywords | List discovered keywords |
| GET | /api/keywords/stats | Keyword stats |
| PATCH | /api/keywords/{id}/approve | Approve keyword |
| PATCH | /api/keywords/{id}/reject | Reject keyword |
| GET | /api/audit | Paginated audit log |
| GET | /api/dashboard | Executive aggregate stats |

Auth endpoints (no global auth required): `/api/auth/setup-required`, `/api/auth/setup`, `/api/auth/login`, `/api/auth/me`, `/api/auth/users` (CRUD).

## File Structure (Web Tool)

```
backend/
├── app/
│   ├── main.py              FastAPI app, CORS, auth, rate limiter
│   ├── worker.py            Celery app + beat_schedule
│   ├── core/
│   │   ├── config.py        Settings (all env vars)
│   │   ├── deps.py          DB engine, session factory, Redis, init_db
│   │   ├── auth.py          verify_api_key dependency
│   │   ├── limiter.py       slowapi instance
│   │   ├── storage.py       S3/R2 evidence abstraction
│   │   ├── audit.py         log_action() helper
│   │   ├── notifications.py Email + Slack notifications
│   │   └── webhook.py       BSSN/CSIRT webhook
│   ├── api/routes/
│   │   ├── scan.py          Scan + lifecycle + trend + bulk + cancel
│   │   ├── report.py        HTML + PDF report export
│   │   ├── schedules.py     Schedule CRUD
│   │   ├── keywords.py      Keyword management
│   │   ├── audit.py         Audit log endpoint
│   │   ├── dashboard.py     Executive dashboard
│   │   └── auth.py          Setup/login/users CRUD
│   ├── scanner/
│   │   ├── pipeline.py      Module registry + runner + diff + webhook
│   │   ├── scoring.py       CVSS-lite scoring
│   │   ├── dork_sweep.py    Google CSE dorks
│   │   ├── page_crawl.py    Playwright injection detector
│   │   ├── header_probe.py  Security header analysis
│   │   ├── path_probe.py    Exposed path detection
│   │   ├── cms_detect.py    CMS fingerprinting
│   │   ├── shodan_probe.py  Shodan API (optional)
│   │   ├── subdomain_enum.py  crt.sh + DNS probe
│   │   ├── keyword_discovery.py  Auto-discovery
│   │   └── keywords.py      Gambling term lists
│   ├── tasks/
│   │   ├── scan_tasks.py    Single domain pipeline
│   │   ├── tld_sweep_tasks.py  TLD sweep + child dispatch
│   │   ├── schedule_tasks.py   Beat: dispatch due schedules
│   │   └── retention_tasks.py  Beat: purge old data (daily)
│   ├── models/scan.py       All SQLAlchemy models
│   └── schemas/             Pydantic v2 schemas
frontend/
├── src/
│   ├── App.jsx              Routes: / /scan/:id /keywords /history /schedules /dashboard /audit /users
│   ├── lib/api.js           Axios client, X-API-Key interceptor
│   ├── pages/               8 pages
│   └── components/          Input, results, shared
```

## Severity Scoring

| Severity | CVSS-lite base |
| --- | --- |
| Critical | 9.0-9.8 |
| High | 6.5-8.5 |
| Medium | 4.5-5.5 |
| Low | 3.0 |
| Info | 1.0 |

Evidence modifiers: +0.3 screenshot, +0.4 >=10 keywords, +0.2 >=5 keywords, +0.3 >=3 injected links. Capped at 10.0.

## Conventions

- Python: type hints, async routes, Pydantic v2
- React: functional components, custom hooks, Tailwind only (no shadcn, no Framer Motion)
- Evidence files: `{scan_id}_{module}_{url_slug}_{timestamp}.png`
- Commits: conventional commits (feat:, fix:, chore:, docs:)
- Comments: English only
- No em dashes - use hyphens
- All user input HTML-escaped before rendering

## Do Not Touch

- `backend/` and `frontend/` code unless explicitly asked
- `data/` folder (gitignored, never commit)
- `main` branch pipeline code (stable tool)
- Statistical methodology (scoped for specific research design)

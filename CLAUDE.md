# CLAUDE.md - PantauInd Web Tool

## What This Project Is

PantauInd is a personal security project by Calvin Wirathama Katoroy (Computer Engineering, Universitas Indonesia). This branch hosts the **web scanner tool** - a FastAPI + React application that detects gambling SEO injection and passive vulnerability surfaces on `.go.id` / `.ac.id` domains.

The accompanying empirical research (national-scale data collection and statistical analysis CLI) lives on the `research-pipeline` branch.

The problem: thousands of Indonesian government websites are compromised with gambling SEO injection. This tool sweeps the namespace, surfaces evidence with CVSS-lite scores and screenshots, and produces PDF reports for disclosure to BSSN / Komdigi.

## Repository Branches

- `main` - stable web tool baseline
- `web-tool` - active web tool development (this branch)
- `research-pipeline` - separate CLI pipeline for thesis data collection

## Architecture

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

## Absolute Constraints

- **Passive recon ONLY** - GET requests, zero payload injection, no active exploitation
- **Python 3.11+**
- **Windows compatible** (d:/pantauin) AND Linux portable
- **No em dashes** - use hyphens in all source code, comments, and documentation
- **No ML for detection** - rule-based keyword matching is deliberate (explainability for evidence)
- **Scraper contract** - every scanner module returns: `{"module": "<name>", "status": "success"|"error"|"skipped", "findings": [...]|null, "error": "..."|null}`
- **Module registry** - adding a scanner = create file + add PipelineModule to PIPELINE list
- **Shodan is conditional** - only active when SHODAN_API_KEY is set, no ghost ModuleStatus rows
- **Celery beat: single instance** - never scale > 1
- **No supervisor mentioned** - this is a personal project

## Key Design Decisions

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

## Severity Scoring

| Severity | CVSS-lite base |
| --- | --- |
| Critical | 9.0-9.8 |
| High | 6.5-8.5 |
| Medium | 4.5-5.5 |
| Low | 3.0 |
| Info | 1.0 |

Evidence modifiers: +0.3 screenshot, +0.4 >=10 keywords, +0.2 >=5 keywords, +0.3 >=3 injected links. Capped at 10.0.

## API Endpoints

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

## File Structure

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

## Conventions

- Python: type hints, async routes, Pydantic v2
- React: functional components, custom hooks, Tailwind only (no shadcn, no Framer Motion)
- Evidence files: `{scan_id}_{module}_{url_slug}_{timestamp}.png`
- Commits: conventional commits (feat:, fix:, chore:, docs:)
- Comments: English only
- No em dashes - use hyphens
- All user input HTML-escaped before rendering

## Do Not Touch

- `data/` folder if present (gitignored, never commit)
- Statistical methodology (lives on `research-pipeline` branch, not here)

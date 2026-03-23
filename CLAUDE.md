# PantauInd — Indonesian Government & Academic Website Security Scanner
## Project Context for Claude Code

---

## What this project is

PantauInd is an Indonesia-focused automated scanner that detects online gambling
content injection and passive vulnerability surfaces on Indonesian government
(.go.id) and academic (.ac.id) websites.

**The problem it solves:** Indonesia has a systemic, large-scale problem where
government and academic websites are compromised and injected with online
gambling (judi online) content — SEO spam, hidden links, redirects, defaced
pages. These go undetected for months because no automated tool sweeps the
entire .go.id / .ac.id namespace and reports them in one place.

**Secondary problem:** Many of these same sites expose passive vulnerability
surfaces — outdated CMS versions, exposed admin panels, missing security
headers, directory listing enabled — that enabled the compromise in the first
place. PantauInd surfaces these as an actionable remediation report.

**Who uses it:**
- BSSN (Badan Siber dan Sandi Negara) analysts
- Government IT teams doing self-assessment
- Investigative journalists covering judi online infiltration of .go.id
- CTI analysts and blue teamers
- Academic researchers studying Indonesian web security posture

**Why it's novel:**
- No existing tool sweeps the .go.id / .ac.id namespace specifically
- Combines gambling injection detection + passive vuln surface in one report
- Indonesian-context keyword lists (bahasa Indonesia gambling terms)
- Evidence snapshots (Playwright screenshot + timestamp) per finding — court-admissible
- CVSS-lite numeric scores per finding for prioritisation

---

## Tech Stack

| Layer | Tech | Notes |
|---|---|---|
| Frontend | React 18 + Tailwind CSS (Vite) | Dark theme |
| Backend API | FastAPI (Python 3.11+) | Async, Pydantic v2 |
| Scraping | Playwright (async) | Screenshots + JS-rendered pages |
| HTTP probing | httpx | Header analysis, path probing, Shodan API |
| Search | Google Custom Search API | Dork queries for gambling keywords |
| NLP/matching | Regex + keyword lists | Bahasa Indonesia gambling terms |
| Database | SQLite (local dev) → PostgreSQL (prod, asyncpg) | Scan result storage |
| PDF Export | WeasyPrint | Print-optimised white-background reports |
| Task Queue | Celery + Redis | Parallel domain scanning |
| Rate limiting | slowapi | Per-IP limits on scan endpoints |
| Auth | API key (X-API-Key header) | Disabled when API_KEY env is empty |
| Deployment | Docker Compose → Fly.io | Fly.io not yet configured |

---

## Scan Modules

### Module 1 — Gambling Injection Detector
Detects judi online content injected into .go.id / .ac.id pages.

**Method A — Dork sweep (passive):**
Google CSE dork queries against target namespace:
- `site:.go.id "judi online"`
- `site:.go.id "slot gacor"`
- `site:.go.id "togel"`
- `site:.ac.id "judi"`
- etc. (full keyword list in `scanner/keywords.py`)

Returns: list of flagged URLs with Google snippet as initial evidence.

**Method B — Direct page crawl (active, Playwright):**
For each flagged URL from Method A (or user-supplied domain):
- Load page with Playwright
- Extract full text content
- Run keyword matcher against Indonesian gambling term list
- Take timestamped screenshot as evidence
- Extract injected `<a>` tags (hidden links, keyword-stuffed anchors)
- Detect `<meta>` redirect or JS redirect to gambling domains

Returns: per-page finding with severity, evidence text, screenshot path,
detected keywords, injected link samples, CVSS-lite score.

### Module 2 — Passive Vulnerability Surface
Passive (non-intrusive) checks only — no active exploitation.

**HTTP header analysis (httpx):**
- Missing security headers: `X-Frame-Options`, `X-Content-Type-Options`,
  `Content-Security-Policy`, `Strict-Transport-Security`, `Referrer-Policy`
- Server version disclosure: `Server: Apache/2.2.x`, `X-Powered-By: PHP/5.x`
- HTTPS enforcement (HTTP → HTTPS redirect present?)
- Cookie flags: `Secure`, `HttpOnly`, `SameSite`

**Exposed path probing (httpx):**
Non-intrusive: only checks for 200/403 response on common paths:
- `/wp-admin/`, `/wp-login.php` (WordPress — very common on .go.id)
- `/administrator/` (Joomla)
- `/phpmyadmin/`, `/pma/`
- `/.env`, `/.git/config`, `/config.php`
- `/admin/`, `/login/`, `/dashboard/`
- `/backup/`, `/db/`, `/sql/`

**CMS fingerprinting:**
- WordPress: detect `wp-content/`, `wp-includes/`, generator meta tag
- Joomla: detect `/components/com_`, generator meta
- Drupal: detect `sites/default/files/`

Returns: per-domain vulnerability surface report with severity ratings.

### Module 3 — Evidence Snapshot
For every confirmed finding (gambling injection or critical vuln surface):
- Playwright full-page screenshot (PNG, timestamped filename)
- Page HTML snapshot (saved locally, not served externally)
- Metadata: URL, scan timestamp (WIB), HTTP status, final redirected URL
- Hash (SHA256) of screenshot for integrity/chain-of-custody

---

### Module 4 — Shodan Probe (optional)
Only runs when `SHODAN_API_KEY` is configured. Skipped silently otherwise —
no ghost module status rows created when key is absent.

- Resolves domain to IP via DNS
- Queries Shodan host API for open ports, service banners, CVEs
- High severity: exposed DB/cache ports (MySQL 3306, Redis 6379, MongoDB 27017, etc.)
- Medium severity: FTP, Telnet, RDP, VNC, SMB
- Critical/High: Shodan-detected CVEs with CVSS ≥ 7.0
- Info: open port inventory summary

---

## Architecture

```
React Frontend
    REST (polling /scan/{id} every 2s)
    AuthGate — checks localStorage for API key, prompts on first visit
FastAPI Backend
    All routes gated by verify_api_key dependency (disabled when API_KEY is empty)
    Rate limited: POST /scan 10/min, POST /scan/bulk 3/min (slowapi, per-IP)
    POST /scan              — start scan (single domain or TLD sweep)
    DELETE /scan/{id}       — cancel scan (revokes Celery task, sets status=cancelled)
    GET  /scan/{id}         — poll status + partial results + children
    GET  /scans             — paginated scan history
    GET  /trend             — per-scan finding counts for a domain over time
    POST /scan/bulk         — CSV upload, dispatches one scan per domain
    GET  /scan/{id}/report  — export HTML report
    GET  /scan/{id}/report/pdf — export PDF report (WeasyPrint)
    dispatches Celery tasks, each module writes results to DB as it completes
    evidence files stored in backend/evidence/{scan_id}/
    webhook: POST to WEBHOOK_URL on Critical findings (non-fatal if fails)

Celery Worker (separate process/container)
    scan_tasks.run_scan         — single domain: runs full pipeline
    tld_sweep_tasks.run_tld_sweep — TLD sweep: dork namespace, dispatch child run_scan per domain
    celery_task_id stored on ScanJob for cancellation via control.revoke()

Scan Pipeline (scanner/pipeline.py — module registry pattern):
    PIPELINE = [dork_sweep, page_crawl, header_probe, path_probe, cms_detect, shodan_probe]
    Generic runner loop — adding a new module = create file + append to PIPELINE list
    Each module error is caught individually; one failure does not abort the scan
    shodan_probe only added to active_modules when SHODAN_API_KEY is set

CVSS-lite scoring (scanner/scoring.py):
    Computed in _save_findings for every finding
    Base score from severity label → module-specific override → evidence modifiers
    Stored as Finding.cvss_score (float, 0.0–10.0)

Infrastructure (docker-compose):
    postgres:16-alpine  — persistent storage (healthcheck gated)
    redis:7-alpine      — Celery broker + result backend
    backend             — FastAPI (uvicorn)
    celery_worker       — Celery worker (concurrency=4)
    frontend            — Vite dev server
```

---

## Input Types

| Input | Example | Behavior |
|---|---|---|
| Single domain | `bkn.go.id` | Full pipeline scan (6 modules) |
| TLD sweep | `.go.id` | Dork sweep entire namespace, dispatch child scan per unique domain (max 50) |
| Bulk CSV | `domains.csv` | One domain per row, dispatches scan per domain via POST /scan/bulk |

Input starting with `.` is auto-detected as TLD sweep mode in both frontend and backend.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/scan` | Start scan. Body: `{"domain": "bkn.go.id"}`. Rate: 10/min |
| DELETE | `/api/scan/{id}` | Cancel running/pending scan. Revokes Celery task |
| GET | `/api/scan/{id}` | Poll scan status, findings, module progress, child scans |
| GET | `/api/scans` | Scan history. Query params: `page`, `limit`, `status`, `domain` |
| GET | `/api/trend` | Domain trend. Query param: `domain`. Returns per-scan finding counts |
| POST | `/api/scan/bulk` | CSV upload. Multipart `file` field. Rate: 3/min |
| GET | `/api/scan/{id}/report` | Download HTML report |
| GET | `/api/scan/{id}/report/pdf` | Download PDF report |
| GET | `/api/keywords` | List discovered keywords |
| GET | `/api/keywords/stats` | Keyword stats |
| PATCH | `/api/keywords/{id}/approve` | Approve auto-discovered keyword |
| PATCH | `/api/keywords/{id}/reject` | Reject auto-discovered keyword |

All endpoints require `X-API-Key` header when `API_KEY` env var is set.

---

## Project Phases

### Phase 1 — MVP ✓ COMPLETE

- FastAPI backend with async scan pipeline
- All 5 scanner modules: dork_sweep, page_crawl, header_probe, path_probe, cms_detect
- React frontend: scan input → progress → FindingCards with severity badges
- Evidence screenshots + SHA256 hashing
- HTML report export
- Keyword auto-discovery system

### Phase 2 — TLD Sweep + Full Vuln Surface ✓ COMPLETE

- Celery + Redis task queue (replaces BackgroundTasks)
- Module registry pattern (scanner/pipeline.py)
- TLD sweep mode with parallel child scan dispatch
- Scan history endpoint with pagination and finding counts
- PDF report export (WeasyPrint, print-optimised)
- CVSS-lite numeric severity scoring (0.0–10.0)
- PostgreSQL support (asyncpg); docker-compose auto-injects prod URL

### Phase 3 — Dashboard + Intelligence + Pre-deploy Polish ✓ COMPLETE

- Trend tracking: GET /api/trend + SVG TrendChart on History page
- Bulk CSV upload: POST /api/scan/bulk + drag-and-drop UI on Home
- BSSN/CSIRT webhook: POST on Critical findings (WEBHOOK_URL env var)
- Shodan integration: 6th pipeline module, skipped when key absent
- API key auth: X-API-Key header + AuthGate frontend component
- Rate limiting: slowapi, per-IP on scan endpoints
- Scan cancellation: DELETE /api/scan/{id}, Celery task revoke, Cancel button
- ScanReport trend link: shows "N scans — view trend →" when domain has history
- History page: pre-fills domain search from ?domain= URL param

### Phase 4 — Production Hardening

Priority order — must be done before Fly.io deployment or sharing with BSSN.

- ✓ **DB indexes** — indexes added on ScanJob(domain, status, parent_id, created_at)
  and Finding(scan_job_id, severity) via SQLAlchemy `Index()` in models/scan.py.
- ✓ **Redis caching for completed scans** — GET /scan/{id} serves from Redis for
  terminal-status scans; 300s TTL; non-fatal fallback to DB if Redis unavailable.
- **Fly.io deployment** — fly.toml, secrets config, persistent volume for evidence
- **GitHub Actions CI/CD** — lint + build on push, deploy to Fly.io on main merge
- **Data retention policy** — archive or delete scans + evidence older than N days;
  evidence dir grows unbounded currently
- ✓ **Connection pool tuning** — pool_size=20, max_overflow=10, pool_pre_ping=True
  applied for PostgreSQL in deps.py (SQLite dev path unchanged).
- **S3/R2 for evidence storage** — local filesystem blocks horizontal backend scaling;
  screenshot_path becomes object key, served via presigned URLs

### Phase 5 — Monitoring Platform

Transforms PantauInd from a one-shot tool into an operational monitoring platform.

- **Scheduled/recurring scans** — cron-based: set a domain to scan weekly,
  alert on new findings. Most impactful single feature for BSSN use case.
- **Finding lifecycle** — open → in-remediation → resolved → accepted-risk.
  Without this, there is no way to track whether a compromised site was cleaned.
- **Scan diff / delta reports** — "since last scan: 3 new critical, 2 resolved"
- **Multi-user + RBAC** — analyst / read-only / admin roles. Single API key
  does not scale to a team.
- **Audit log** — who triggered what scan, when, from which IP
- **Email + Slack notifications** — alongside existing webhook
- **Finding filter/sort on ScanReport** — scans with 80+ findings need
  client-side filter by severity/module/keyword
- **Executive dashboard** — aggregate view: total domains affected, critical
  count over time, top recurring gambling injection targets
- **Subdomain enumeration** — scan subdomains of a root domain, not just root

### Out of scope (by design)

- **Machine learning** — rule-based keyword detection is sufficient for this
  problem domain. Gambling injection uses consistent, known Bahasa Indonesia terms.
  `keyword_discovery.py` handles new slang organically without ML infrastructure.
  ML would add training data requirements, model maintenance, and reduced
  explainability — the last point matters for court-admissible evidence.
- **Active exploitation** — passive only. No payload injection, no active CVE testing.
- **Non-.go.id / non-.ac.id domains** — scope is Indonesian government and academic.

---

## File Structure

```
pantauind/
├── CLAUDE.md
├── .env.example
├── docker-compose.yml
├── backend/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── app/
│       ├── main.py                ← FastAPI app, CORS, auth dependency, rate limiter
│       ├── worker.py              ← Celery app instance
│       ├── core/
│       │   ├── config.py          ← Settings (database_url, redis, CSE, api_key, webhook, shodan)
│       │   ├── deps.py            ← DB engine, session factory, init_db
│       │   ├── auth.py            ← verify_api_key FastAPI dependency
│       │   ├── limiter.py         ← slowapi Limiter instance
│       │   └── webhook.py         ← notify_webhook() async, non-fatal
│       ├── api/routes/
│       │   ├── scan.py            ← all scan endpoints + trend + bulk + cancel
│       │   ├── report.py          ← GET /scan/{id}/report (HTML + PDF)
│       │   └── keywords.py        ← keyword management endpoints
│       ├── scanner/
│       │   ├── pipeline.py        ← module registry + generic pipeline runner + webhook trigger
│       │   ├── scoring.py         ← CVSS-lite scoring function
│       │   ├── dork_sweep.py      ← Google CSE gambling dorks
│       │   ├── page_crawl.py      ← Playwright injection detector + screenshot
│       │   ├── header_probe.py    ← httpx security header analysis
│       │   ├── path_probe.py      ← httpx exposed path detection
│       │   ├── cms_detect.py      ← CMS fingerprinting
│       │   ├── shodan_probe.py    ← Shodan host API: ports, CVEs, banners
│       │   ├── keyword_discovery.py ← auto-discovery of new gambling terms
│       │   └── keywords.py        ← Bahasa Indonesia gambling term lists
│       ├── tasks/
│       │   ├── scan_tasks.py      ← Celery task: single domain pipeline
│       │   └── tld_sweep_tasks.py ← Celery task: TLD sweep + child dispatch
│       ├── models/
│       │   └── scan.py            ← ScanJob (+ celery_task_id), Finding, ModuleStatus, DiscoveredKeyword
│       └── schemas/
│           ├── scan.py            ← ScanRequest, ScanStatusResponse, ScanHistoryResponse,
│           │                         TrendPoint, TrendResponse, BulkScanResponse
│           └── finding.py         ← FindingSchema with cvss_score
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx                ← wrapped in AuthGate
        ├── lib/api.js             ← axios client + X-API-Key interceptor + 401 handler
        ├── hooks/
        │   ├── useScan.js         ← submit scan, navigate to report
        │   └── useScanJob.js      ← poll scan status every 2s (terminal: completed|error|cancelled)
        ├── pages/
        │   ├── Home.jsx           ← scan input + bulk CSV drag-and-drop upload
        │   ├── ScanReport.jsx     ← findings, cancel button, trend link, severity cards
        │   ├── History.jsx        ← scan history + TrendChart (shown on domain search)
        │   │                         reads ?domain= URL param on mount
        │   └── Keywords.jsx       ← keyword management UI
        └── components/
            ├── input/DomainInput.jsx
            ├── results/
            │   ├── ScanProgress.jsx
            │   ├── FindingCard.jsx
            │   ├── EvidenceViewer.jsx
            │   ├── TrendChart.jsx       ← pure SVG stacked bar chart, no external libs
            │   └── VulnSurface.jsx
            └── shared/
                ├── SeverityBadge.jsx
                ├── AuthGate.jsx         ← API key prompt, stores in localStorage
                └── NavBar.jsx
```

---

## Key Design Decisions (do not revisit)

- **Passive only for vuln surface:** No active exploitation, no payload injection.
  Path probing is GET-only, checking HTTP status codes.
- **Playwright for evidence:** Screenshots are the primary deliverable — they
  must be timestamped, full-page, and SHA256-hashed for integrity.
- **Bahasa Indonesia keyword list is authoritative:** A separate `keywords.py`
  module maintains the gambling term list so it can be updated independently
  of scan logic. `keyword_discovery.py` auto-expands it from found pages.
- **No ML for detection:** Rule-based keyword matching is sufficient and preferable.
  Explainability matters — a keyword match is auditable evidence; a model score is not.
  `keyword_discovery.py` handles new gambling slang organically.
- **Scraper contract:** Every scanner module MUST return this shape even on failure:
  `{"module": "dork_sweep", "status": "error"|"success"|"skipped", "findings": []|null, "error": "..."|null}`
- **Module registry:** Adding a new scanner = create the file following the contract,
  then add one `PipelineModule` entry to `PIPELINE` in `scanner/pipeline.py`.
  Do NOT add hardcoded blocks to the pipeline runner.
- **Shodan is conditional:** Only add shodan_probe to active_modules when
  `settings.shodan_api_key` is set. Never create ghost ModuleStatus rows for
  skipped modules — it creates noise in the UI.
- **Evidence stored server-side:** Screenshots are saved to
  `backend/evidence/{scan_id}/` and served via a static file endpoint.
  Phase 4 migrates this to S3/R2 for horizontal scaling.
- **TLD sweep auto-detection:** Input starting with `.` is a TLD sweep.
  Validated in both `ScanRequest.clean_domain` (backend) and `DomainInput.jsx` (frontend).
- **Celery task pattern:** Tasks are sync functions that call `asyncio.run()` on
  the async implementation. Do not use Celery's experimental asyncio support.
  Store `.delay()` result's `.id` as `ScanJob.celery_task_id` for cancellation.
- **Database:** SQLite (`sqlite+aiosqlite`) for local dev without Docker.
  PostgreSQL (`postgresql+asyncpg`) for prod. docker-compose injects
  `DATABASE_URL` as an environment override — do not hardcode it.
- **Pydantic v2:** Use `model_validator`, `field_validator` (not v1 syntax).
- **Dark UI:** bg `#0a0c0f`, surface `#111318`, border `#2a2d35`, accent `#e8c547`.
  Font: DM Sans (body), Syne (brand/headings), JetBrains Mono (URLs/hashes/code).
- **CVSS-lite scores:** Computed in `_save_findings` via `scoring.compute_cvss_lite()`.
  Stored on `Finding.cvss_score`. Displayed on FindingCard and in both report formats.
- **Auth:** Single shared `API_KEY` env var. Leave empty to disable for local dev.
  Frontend stores key in localStorage; 401 response clears it and reloads (AuthGate re-shows).
  Phase 5 replaces this with multi-user RBAC.
- **Rate limiting:** slowapi, per source IP. Limits are intentionally generous
  (10/min scan, 3/min bulk) to allow legitimate analyst workflows.

---

## Known Scalability Constraints (Phase 4 targets)

These are known limitations, not bugs. Do not work around them — fix them properly in Phase 4.

1. ✓ **DB indexes resolved** — `Index()` definitions added to ScanJob and Finding
   in models/scan.py. ScanJob indexed on domain, status, parent_id, created_at;
   Finding indexed on scan_job_id, severity.
2. **Local evidence storage** — blocks horizontal backend scaling. Fix: S3/R2.
3. ✓ **Completed-scan cache resolved** — GET /scan/{id} caches terminal-status
   responses in Redis (SCAN_CACHE_TTL=300s); non-fatal fallback to DB.
4. **Playwright not pooled** — one Chromium instance per page_crawl invocation.
   Under TLD sweep load (50 child scans), memory pressure is significant.
5. **Single Redis** — no HA. Fix: Redis Sentinel or managed Redis in prod.
6. **Google CSE quota** — 100 queries/day free. No dork result caching.
   Same TLD swept twice in a day burns quota twice.

---

## Gambling Keyword List (seed — expand in keywords.py)

Indonesian terms:
`judi online`, `judi bola`, `slot gacor`, `slot online`, `togel`, `toto`,
`situs judi`, `agen judi`, `bandar judi`, `poker online`, `casino online`,
`taruhan bola`, `bocoran slot`, `RTP slot`, `link alternatif`, `daftar slot`,
`maxwin`, `pragmatic play`, `pg soft`, `gacor hari ini`

Common injected anchor patterns:
`slot`, `gacor`, `138`, `777`, `303`, `4d`, `sgp`, `hk`, `sydney`

---

## Severity Scoring

| Severity | Criteria | CVSS-lite base |
| --- | --- | --- |
| Critical | Gambling content confirmed on page (keywords + screenshot) | 9.0–9.8 |
| High | Hidden gambling links injected / Exposed `.env`, `.git/config` | 6.5–8.5 |
| Medium | Admin panel exposed / Server version disclosure | 4.5–5.5 |
| Low | Missing security headers (CSP, HSTS, X-Frame-Options) | 3.0 |
| Info | CMS fingerprint only (no vulnerability, just detection) | 1.0 |

Evidence modifiers applied on top: +0.3 screenshot confirmed, +0.2 ≥5 keywords,
+0.3 ≥3 injected links. All capped at 10.0.

---

## Conventions

- Python: type hints everywhere, async FastAPI routes, Pydantic v2 models
- React: functional components only, custom hooks for data fetching, Tailwind only (no shadcn, no Framer Motion)
- Evidence files: named `{scan_id}_{module}_{url_slug}_{timestamp}.png`
- Commits: conventional commits (feat:, fix:, chore:)
- Comments: English only
- All user-supplied input HTML-escaped before rendering

---

## Developer Context

Solo project. Stack: Python, FastAPI, React, Tailwind, Playwright, httpx.
Cybersecurity background: Blue Team Lead, Wazuh GAN-DDoS research.
Reference projects:
- IntelID (d:/IntelID) — same stack, borrow patterns (job polling, scraper contract,
  result caching, report export, dark UI components)
- Nexzy — dark web credential monitoring, similar async scraping patterns

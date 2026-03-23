# Pantauin — Indonesian Government & Academic Website Security Scanner
## Project Context for Claude Code

---

## What this project is

Pantauin is an Indonesia-focused automated scanner that detects online gambling
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
place. Pantauin surfaces these as an actionable remediation report.

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

---

## Tech Stack

| Layer | Tech | Notes |
|---|---|---|
| Frontend | React 18 + Tailwind CSS (Vite) | Dark theme, consistent with IntelID |
| Backend API | FastAPI (Python 3.11+) | Async, Pydantic v2 |
| Scraping | Playwright (async) | Screenshots + JS-rendered pages |
| HTTP probing | httpx | Header analysis, path probing |
| Search | Google Custom Search API | Dork queries for gambling keywords |
| NLP/matching | Regex + keyword lists | Bahasa Indonesia gambling terms |
| Database | SQLite (local dev) → PostgreSQL (prod) | Scan result caching |
| PDF Export | WeasyPrint | Formatted security reports |
| Task Queue | Celery + Redis (Phase 2) | Parallel domain scanning |
| Deployment | Docker Compose → Fly.io | |

---

## Scan Modules

### Module 1 — Gambling Injection Detector
Detects judi online content injected into .go.id / .ac.id pages.

**Method A — Dork sweep (passive):**
Google CSE dork queries against target namespace:
- `site:.go.id "judi online"`
- `site:.go.id "slot gacor"`
- `site:.go.id "togel"`
- `site:.go.id "situs slot"`
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

Returns: per-page finding with severity (critical/high/medium), evidence text,
screenshot path, detected keywords, injected link samples.

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

## Architecture

```
React Frontend
    REST (polling /scan/{id}/status every 2s)
FastAPI Backend
    POST /scan         — start a scan job (domain or TLD sweep)
    GET  /scan/{id}    — poll status + partial results
    GET  /scan/{id}/report — export HTML/PDF report
    dispatches async scan tasks per module
    each module writes results to DB as it completes
    evidence files stored in backend/evidence/{scan_id}/

Scan Pipeline (sequential for MVP, Celery in Phase 2):
    1. dork_sweep      — Google CSE → flagged URLs
    2. page_crawl      — Playwright → per-page injection analysis + screenshot
    3. header_probe    — httpx → security header grades
    4. path_probe      — httpx → exposed paths
    5. cms_fingerprint — httpx → CMS detection
```

---

## Input Types

| Input | Example | Behavior |
|---|---|---|
| Single domain | `bkn.go.id` | Scan that domain only |
| TLD sweep | `.go.id` | Dork sweep entire namespace, crawl all hits |
| Ministry prefix | `kemenkeu.go.id` | Scan domain + all known subdomains |
| Custom dork | `site:go.id "slot gacor"` | Direct dork, crawl hits |

---

## Project Phases

### Phase 1 — MVP (BUILD FIRST)
Scope: single domain scan
1. FastAPI backend with sequential async scan pipeline
2. Modules: dork_sweep + page_crawl (gambling detection only)
3. React frontend: DomainInput → scan progress → FindingCards
4. Evidence screenshots saved locally
5. Basic HTML report export

### Phase 2 — TLD Sweep + Full Vuln Surface
- TLD sweep mode (.go.id / .ac.id namespace)
- header_probe + path_probe + cms_fingerprint modules
- Celery + Redis for parallel domain scanning
- Severity scoring system (CVSS-lite)
- Full PDF report (WeasyPrint)

### Phase 3 — Dashboard + BSSN Integration
- Persistent scan history dashboard
- Trend tracking (same domain scanned over time)
- Bulk domain list upload (CSV)
- Optional: BSSN/CSIRT notification webhook
- Optional: Shodan integration for exposed service mapping

---

## File Structure

```
pantauin/
├── CLAUDE.md
├── .env.example
├── docker-compose.yml
├── backend/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── app/
│       ├── main.py
│       ├── core/
│       │   ├── config.py
│       │   └── deps.py
│       ├── api/routes/
│       │   ├── scan.py        ← POST /scan, GET /scan/{id}
│       │   └── report.py      ← GET /scan/{id}/report
│       ├── scanner/
│       │   ├── dork_sweep.py  ← Google CSE gambling dorks
│       │   ├── page_crawl.py  ← Playwright injection detector + screenshot
│       │   ├── header_probe.py← httpx security header analysis
│       │   ├── path_probe.py  ← httpx exposed path detection
│       │   ├── cms_detect.py  ← CMS fingerprinting
│       │   └── keywords.py    ← Bahasa Indonesia gambling term lists
│       ├── models/
│       │   └── scan.py        ← SQLAlchemy ORM: ScanJob, Finding, Evidence
│       └── schemas/
│           ├── scan.py        ← Pydantic request/response schemas
│           └── finding.py     ← Finding schema with severity
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── lib/api.js
        ├── hooks/
        │   ├── useScan.js     ← submit scan, get scan_id
        │   └── useScanJob.js  ← poll scan status
        ├── pages/
        │   ├── Home.jsx       ← DomainInput + scan type selector
        │   └── ScanReport.jsx ← findings + evidence viewer
        └── components/
            ├── input/DomainInput.jsx
            ├── results/
            │   ├── ScanProgress.jsx
            │   ├── FindingCard.jsx   ← per-finding with severity badge
            │   ├── EvidenceViewer.jsx← screenshot + metadata
            │   └── VulnSurface.jsx   ← header/path/cms results
            └── shared/
                ├── SeverityBadge.jsx ← critical/high/medium/low/info
                └── NavBar.jsx
```

---

## Key Design Decisions (already made — do not revisit)

- **Passive only for vuln surface:** No active exploitation, no payload injection.
  Path probing is GET-only, checking HTTP status codes. Pantauin is a detection
  and reporting tool, not a penetration testing framework.
- **Playwright for evidence:** Screenshots are the primary deliverable — they
  must be timestamped, full-page, and SHA256-hashed for integrity.
- **Bahasa Indonesia keyword list is authoritative:** A separate `keywords.py`
  module maintains the gambling term list so it can be updated independently
  of scan logic.
- **Scraper contract:** Every scanner module MUST return this shape even on failure:
  `{"module": "dork_sweep", "status": "error"|"success", "findings": []|null, "error": "..."|null}`
- **Evidence stored server-side:** Screenshots are saved to
  `backend/evidence/{scan_id}/` and served via a static file endpoint.
  They are never uploaded to third-party services.
- **Pydantic v2:** Use `model_validator`, `field_validator` (not v1 syntax).
- **Dark UI:** Consistent with IntelID aesthetic.
- **React Flow for Phase 2 graph:** If domain-to-finding relationships need
  visualization later (e.g. gambling network mapping), use @xyflow/react —
  same pattern as IntelID Phase 2.

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

| Severity | Criteria |
|---|---|
| Critical | Gambling content confirmed on page (keywords + screenshot) |
| High | Hidden gambling links injected (`<a>` with gambling keywords, `display:none`) |
| High | Exposed `.env`, `.git/config`, `config.php` (200 response) |
| Medium | Admin panel exposed (200 response on `/wp-admin`, `/administrator`) |
| Medium | Server version disclosure (Apache/PHP version in headers) |
| Low | Missing security headers (CSP, HSTS, X-Frame-Options) |
| Info | CMS fingerprint only (no vulnerability, just detection) |

---

## Conventions

- Python: type hints everywhere, async FastAPI routes, Pydantic v2 models
- React: functional components only, custom hooks for data fetching, Tailwind only
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

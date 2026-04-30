# PantauInd

![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61dafb?style=flat&logo=react&logoColor=black)
![Playwright](https://img.shields.io/badge/Playwright-async-2ead33?style=flat&logo=playwright&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat)

> Passive attack surface profiling and gambling SEO injection detection for Indonesian government domains.

PantauInd started as a side project during Lebaran 2025. I noticed `.go.id` domains showing up in Google results stuffed with slot and judi keywords, got curious about the scale, and built a scanner. What I found was massive - thousands of Indonesian government websites silently compromised with gambling SEO injection. This branch hosts the full-stack web tool: a FastAPI + React application that detects gambling injection and profiles passive vulnerability surfaces on a per-domain or namespace basis.

The accompanying empirical research (national-scale data collection and statistical analysis) lives on the [`research-pipeline`](https://github.com/calvinkatoroy/pantauin/tree/research-pipeline) branch.

---

## Why This Exists

Indonesia has a systemic, large-scale problem: government (`.go.id`) and academic (`.ac.id`) websites are compromised and injected with **judi online** (online gambling) SEO spam - hidden links, keyword-stuffed pages, JavaScript redirects to gambling domains. These compromises go undetected for months because:

- No automated tool sweeps the `.go.id` / `.ac.id` namespace specifically
- The injected content is often **cloaked** - hidden from regular visitors but visible to search engines
- The same sites expose passive vulnerability surfaces (outdated CMS, exposed admin panels, missing security headers) that likely enabled the compromise in the first place

PantauInd is the detection tool half of that picture: scan a domain or sweep an entire TLD, get evidence-grade findings with CVSS-lite scores, lifecycle tracking, and PDF reports.

---

## Features

**Gambling Injection Detection**
- Google dork sweep via Serper.dev API
- Playwright page crawl with Bahasa Indonesia keyword matching
- Hidden link detection, redirect detection
- Full-page evidence screenshots (PNG, timestamped, SHA256-hashed)

**Passive Vulnerability Surface**
- Security header analysis (CSP, HSTS, X-Frame-Options, etc.)
- Server / PHP version disclosure
- Exposed path probing (GET-only): `/wp-admin/`, `/.env`, `/.git/config`, `/phpmyadmin/`
- CMS fingerprinting (WordPress, Joomla, Drupal)
- Shodan integration (optional) - open ports, CVEs
- Subdomain enumeration via crt.sh + DNS

**Platform**
- TLD sweep mode (`.go.id` scans entire namespace, dispatches child scans)
- Bulk CSV upload
- Scheduled recurring scans (daily / weekly / monthly via Celery beat)
- Finding lifecycle tracking (open / in-remediation / resolved / accepted-risk)
- Scan diff (new vs. recurring vs. resolved between runs)
- CVSS-lite scoring (0.0-10.0) per finding
- HTML and PDF report export
- Executive dashboard, audit log
- Multi-user RBAC (admin / analyst / read-only)
- Webhook, email, and Slack notifications on critical findings

---

## Quick Start

```bash
git clone https://github.com/calvinkatoroy/pantauin.git
cd pantauin

cp .env.example .env
# Edit .env - add SERPER_API_KEY (https://serper.dev, 2500 free credits)

# Backend
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Or run the full stack with Docker:

```bash
docker compose up --build
```

---

## Architecture

```
React Frontend (Vite + Tailwind)
    |  polls GET /api/scan/{id} every 2s
    v
FastAPI Backend
    Auth: multi-user RBAC (X-API-Key) or legacy single key
    Rate limited: 10/min scan, 3/min bulk (slowapi)
    |
    v
Celery Worker (concurrency=4)
    |
    v
Scan Pipeline (module registry):
    dork_sweep -> page_crawl -> header_probe -> path_probe ->
    cms_detect -> shodan_probe (optional) -> subdomain_enum
    |
    v
_compute_diff() + _save_findings() + CVSS-lite scoring

Infrastructure: PostgreSQL 16, Redis 7, Celery Beat (single instance)
```

---

## Repository Structure

```
pantauin/
├── .github/workflows/         CI/CD (lint, build, deploy)
├── backend/                   FastAPI backend (Python 3.11+)
│   ├── app/
│   │   ├── api/routes/        REST endpoints
│   │   ├── core/              Config, auth, storage, audit
│   │   ├── scanner/           7-module scan pipeline
│   │   ├── tasks/             Celery tasks + beat schedules
│   │   └── models/            SQLAlchemy models
│   ├── alembic/               Database migrations
│   └── tests/                 71 tests (pytest)
├── frontend/                  React 18 + Tailwind CSS (Vite)
├── docker-compose.yml         Full stack (Postgres, Redis, Celery)
└── fly.toml                   Fly.io deployment (sin region)
```

---

## Severity Scale

| Severity | Criteria | CVSS-lite |
| --- | --- | --- |
| Critical | Gambling content confirmed on page (keywords + screenshot) | 9.0-9.8 |
| High | Hidden gambling links / exposed `.env`, `.git/config` | 6.5-8.5 |
| Medium | Admin panel exposed / server version disclosure | 4.5-5.5 |
| Low | Missing security headers | 3.0 |
| Info | CMS fingerprint only | 1.0 |

---

## API

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/scan` | Start scan (single domain or TLD sweep) |
| GET | `/api/scan/{id}` | Poll status + findings (Redis cached) |
| DELETE | `/api/scan/{id}` | Cancel scan |
| GET | `/api/scans` | Scan history (paginated) |
| GET | `/api/trend` | Domain trend over time |
| POST | `/api/scan/bulk` | CSV upload |
| GET | `/api/scan/{id}/report/pdf` | PDF report |
| PATCH | `/api/finding/{id}/lifecycle` | Update finding status |
| POST | `/api/schedules` | Create recurring scan |
| GET | `/api/dashboard` | Executive stats |
| GET | `/api/audit` | Audit log |

Auth endpoints at `/api/auth/*`. All endpoints require `X-API-Key` when auth is enabled.

---

## Who This Is For

- Security researchers studying Indonesian web infrastructure
- BSSN / Komdigi analysts
- Government IT teams doing self-assessment
- Investigative journalists covering judi online infiltration
- CTI / blue team analysts

---

## Ethics

Passive recon only. All HTTP probing is GET-only. No payload injection. No active exploitation. Evidence stored locally or in private S3, never uploaded to third-party services. SHA256 hashing for chain-of-custody. BSSN disclosure before any public domain-level findings.

---

## License

MIT

## Disclaimer

PantauInd performs passive, non-intrusive scans only. It is a detection and evidence tool, not a penetration testing framework. Use it only on domains you are authorized to scan.

# PantauInd

![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61dafb?style=flat&logo=react&logoColor=black)
![Playwright](https://img.shields.io/badge/Playwright-async-2ead33?style=flat&logo=playwright&logoColor=white)
![Research](https://img.shields.io/badge/Research-Data%20Collection-blueviolet?style=flat)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat)

> Passive attack surface profiling of gambling SEO-injected Indonesian government domains - personal research project & detection tool

PantauInd started as a side project during Lebaran 2025. I noticed `.go.id` domains showing up in Google results stuffed with slot and judi keywords, got curious about the scale, and built a scanner. What I found was massive - thousands of Indonesian government websites silently compromised with gambling SEO injection. I started reading the academic literature and realized that while several papers had documented the *infection*, nobody had empirically studied *why* these specific domains got infected - what vulnerability characteristics made them susceptible. PantauInd fills that gap: it combines national-scale passive attack surface profiling with gambling SEO injection detection as compromise ground truth, producing the first empirical study bridging these two problems on `.go.id` domains.

---

## Why This Exists

Indonesia has a systemic, large-scale problem: government (`.go.id`) and academic (`.ac.id`) websites are compromised and injected with **judi online** (online gambling) SEO spam - hidden links, keyword-stuffed pages, JavaScript redirects to gambling domains. These compromises go undetected for months because:

- No automated tool sweeps the `.go.id` / `.ac.id` namespace specifically
- The injected content is often **cloaked** - hidden from regular visitors but visible to search engines
- The same sites expose passive vulnerability surfaces (outdated CMS, exposed admin panels, missing security headers) that likely enabled the compromise in the first place

Existing work (Nurseno 2024, Zagi 2025, Riyadi 2025) answers "which domains are infected" but not "why they got infected." I built PantauInd to answer both questions - a detection tool that also profiles the attack surface, producing data suitable for statistical correlation analysis.

---

## Research

**Title:** Attack Surface Profiling of Gambling-Injected Indonesian Government Websites Using Passive Web Reconnaissance: A National-Scale Empirical Study

**Status:** Data collection in progress (April 2026)

**The gap:** Prior work on gambling SEO injection in Indonesia focuses on detection - finding infected domains using dork queries and keyword matching. Meanwhile, attack surface measurement studies (Vasek 2016, Harry 2025, Kovacevic 2022) have shown that vulnerability characteristics like outdated CMS, missing security headers, and exposed admin panels correlate with compromise - but none of these have been applied to Indonesian government domains or to gambling injection specifically. This project bridges both streams.

**Research Questions:**
1. **RQ1:** What is the prevalence and distribution of gambling SEO injection across `.go.id` domains at national scale?
2. **RQ2:** What are the attack surface characteristics (security headers, exposed paths, CMS, version disclosure) of infected vs. clean domains?
3. **RQ3:** Which vulnerability features correlate significantly with gambling SEO injection status?

### Literature Gap

| Paper | .go.id | Gambling | Vuln Profile | Passive | Correlation | National |
| --- | --- | --- | --- | --- | --- | --- |
| Nurseno 2024 (MATRIK) | Yes | Yes | No | Yes | No | Yes |
| Zagi 2025 (ArXiv) | Yes | Yes | No | Yes | No | No |
| Riyadi 2025 (bit-Tech) | Yes | Yes | No | Yes | No | No |
| Teppap 2024 (IEEE JCSSE) | No | Yes | No | Yes | No | No |
| Harry 2025 (J.Cybersecur) | No | No | Yes | Yes | Yes | Yes |
| Kovacevic 2022 (SoftCOM) | No | No | Yes | Yes | Yes | No |
| Kasturi 2023 (IEEE ITNAC) | No | No | Yes | No | Yes | No |
| Vasek 2016 (IEEE TDSC) | No | No | Yes | Yes | Yes | Yes |
| Almaarif 2020 (IJASET) | Yes | No | Yes | No | No | No |
| Darojat 2022 (JSIB) | Yes | No | Yes | No | No | No |
| Suyitno 2024 (ICETIA) | Yes | No | Yes | Yes | No | No |
| GambitHunter 2026 | No | Yes | No | No | No | No |
| MAD-CTI 2025 (IEEE Access) | No | Yes | No | No | No | No |
| **This Study** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |

No existing study combines all six columns.

### Research Pipeline (`research-pipeline` branch)

```
enumerate.py  ->  crt.sh / Subfinder  ->  domains.csv       (20-50k .go.id domains)
detect.py     ->  httpx + BS4         ->  suspected.csv      (bulk keyword scan)
confirm.py    ->  Playwright async    ->  confirmed.csv      (deep confirmation)
surface.py    ->  httpx passive       ->  attack_surface.csv  (all domains profiled)
analysis.py   ->  statsmodels Logit   ->  tables/ + figures/  (chi-square + regression)
```

Key decisions: httpx + BS4 for bulk speed (not Playwright for 50k domains), Playwright only for the ~5% suspected, statsmodels for regression (thesis needs p-values and 95% CI, not sklearn), all domains profiled (infected + clean) for a proper control group. `data/` is gitignored - no domain lists committed.

### Statistical Plan

- Chi-square test per vulnerability feature (Bonferroni corrected)
- Fisher's exact fallback when expected cell < 5
- Logistic regression: odds ratio, 95% CI, p-value, pseudo-R-squared, AIC
- VIF check for multicollinearity

### Responsible Disclosure

Before publishing any domain-level findings, I will report to BSSN (Badan Siber dan Sandi Negara). Aggregate statistics and anonymized data will be published. Raw infected domain lists will not be made public.

---

## Repository Structure

| Branch | Purpose | Status |
| --- | --- | --- |
| `main` | Web scanner tool (FastAPI + React) | Stable |
| `research-pipeline` | Research CLI pipeline (5-stage) | Active development |

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

## Web Tool

### Features

**Gambling Injection Detection**
- Google dork sweep via Serper.dev API
- Playwright page crawl with Bahasa Indonesia keyword matching
- Hidden link detection, redirect detection
- Full-page evidence screenshots (PNG, timestamped, SHA256-hashed)

**Passive Vulnerability Surface**
- Security header analysis (CSP, HSTS, X-Frame-Options, etc.)
- Server/PHP version disclosure
- Exposed path probing (GET-only): `/wp-admin/`, `/.env`, `/.git/config`, `/phpmyadmin/`
- CMS fingerprinting (WordPress, Joomla, Drupal)
- Shodan integration (optional) - open ports, CVEs
- Subdomain enumeration via crt.sh + DNS

**Platform**
- TLD sweep mode (`.go.id` scans entire namespace, dispatches child scans)
- Bulk CSV upload
- Scheduled recurring scans (daily/weekly/monthly via Celery beat)
- Finding lifecycle tracking (open / in-remediation / resolved / accepted-risk)
- Scan diff (new vs. recurring vs. resolved between runs)
- CVSS-lite scoring (0.0-10.0) per finding
- HTML and PDF report export
- Executive dashboard, audit log
- Multi-user RBAC (admin / analyst / read-only)
- Webhook, email, and Slack notifications on critical findings

### Quick Start

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

### Architecture

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

### Severity Scale

| Severity | Criteria | CVSS-lite |
| --- | --- | --- |
| Critical | Gambling content confirmed on page (keywords + screenshot) | 9.0-9.8 |
| High | Hidden gambling links / exposed `.env`, `.git/config` | 6.5-8.5 |
| Medium | Admin panel exposed / server version disclosure | 4.5-5.5 |
| Low | Missing security headers | 3.0 |
| Info | CMS fingerprint only | 1.0 |

### API

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

## Citation

```bibtex
@misc{katoroy2026pantauind,
  author       = {Katoroy, Calvin Wirathama},
  title        = {Attack Surface Profiling of Gambling-Injected Indonesian
                  Government Websites Using Passive Web Reconnaissance:
                  A National-Scale Empirical Study},
  year         = {2026},
  howpublished = {\url{https://github.com/calvinkatoroy/pantauin}},
  note         = {Personal research project. Data collection in progress.}
}
```

## License

MIT

## Disclaimer

PantauInd performs passive, non-intrusive scans only. It is a detection and evidence tool, not a penetration testing framework. Use the web tool only on domains you are authorized to scan. The research pipeline targets `.go.id` as part of responsible security research with planned BSSN disclosure.

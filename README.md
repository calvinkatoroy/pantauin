# Pantauin

> **Indonesian Government & Academic Website Security Scanner**
> Detects judi online (online gambling) content injection and passive vulnerability surfaces on `.go.id` and `.ac.id` domains.

![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61dafb?style=flat&logo=react&logoColor=black)
![Playwright](https://img.shields.io/badge/Playwright-async-2ead33?style=flat&logo=playwright&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat)

---

## The Problem

Indonesia has a systemic, large-scale problem where government (`.go.id`) and academic (`.ac.id`) websites are compromised and injected with **judi online** (online gambling) SEO spam — hidden links, keyword-stuffed pages, and JavaScript redirects to gambling domains.

These compromises go undetected for months because:
- No automated tool sweeps the `.go.id` / `.ac.id` namespace specifically
- The injected content is often **cloaked** — hidden from regular visitors but visible to Google
- The same sites expose passive vulnerability surfaces (outdated CMS, exposed admin panels) that enabled the compromise in the first place

**Pantauin solves this.** It scans a target domain, detects gambling injection with Playwright-captured evidence, and surfaces the vulnerability exposures that likely enabled the attack — all in one report.

---

## Features

### Module 1 — Gambling Injection Detector
- **Google Dork Sweep** — queries `site:target.go.id "slot gacor"`, `"judi online"`, `"togel"` etc. via Google Custom Search API
- **Playwright Page Crawl** — loads pages with a real browser, runs Bahasa Indonesia keyword matching against full page text and raw HTML
- **Hidden link detection** — finds injected `<a>` tags with `display:none` or off-screen CSS
- **Redirect detection** — catches `<meta>` refresh and `window.location` redirects to gambling domains
- **Evidence screenshots** — full-page PNG, timestamped (WIB), SHA256-hashed for integrity

### Module 2 — Passive Vulnerability Surface
- **HTTP header analysis** — missing CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy
- **Version disclosure** — Server/X-Powered-By header leaking Apache/PHP versions
- **Exposed path probing** — GET-only checks for `/wp-admin/`, `/.env`, `/.git/config`, `/phpmyadmin/`, backup dirs, etc.
- **CMS fingerprinting** — WordPress, Joomla, Drupal detection
- **HTTPS enforcement** and cookie flag checks

### Module 3 — Evidence Snapshot
- Full-page Playwright screenshot per finding
- SHA256 hash for chain-of-custody integrity
- WIB-timestamped filenames
- Served via static endpoint, never uploaded to third-party services

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Tailwind CSS (Vite), dark theme |
| Backend | FastAPI (Python 3.11+), async, Pydantic v2 |
| Scraping | Playwright (async) |
| HTTP probing | httpx |
| Search | Google Custom Search API |
| Database | SQLite (dev) → PostgreSQL (prod), SQLAlchemy async |
| Deployment | Docker Compose |

---

## Architecture

```
React Frontend (Vite + Tailwind)
    │  polls GET /api/scan/{id} every 2s
    ▼
FastAPI Backend
    POST /api/scan          → start scan job
    GET  /api/scan/{id}     → poll status + live findings
    GET  /api/scan/{id}/report → export HTML report

Scan Pipeline (sequential async):
    1. dork_sweep      — Google CSE → flagged URLs
    2. page_crawl      — Playwright → injection analysis + screenshots
    3. header_probe    — httpx → security header grades
    4. path_probe      — httpx → exposed path detection
    5. cms_detect      — httpx → CMS fingerprinting
```

---

## Severity Scale

| Severity | Criteria |
|---|---|
| 🔴 Critical | Gambling keywords confirmed on page + screenshot evidence |
| 🟠 High | Hidden gambling `<a>` tags injected / exposed `.env` / `.git/config` |
| 🟡 Medium | Admin panel exposed / server version disclosure |
| 🔵 Low | Missing security headers |
| ⚪ Info | CMS fingerprint only |

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 20+
- Docker & Docker Compose (optional)

### Local Setup

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/pantauin.git
cd pantauin

# Environment
cp .env.example .env
# Edit .env — add GOOGLE_CSE_API_KEY and GOOGLE_CSE_ID if you have them
# (dork sweep is skipped gracefully if not configured)

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

Open [http://localhost:5173](http://localhost:5173)

### Docker

```bash
docker compose up --build
```

---

## Usage

1. Enter a `.go.id` or `.ac.id` domain (e.g. `bkn.go.id`)
2. Watch the scan pipeline run in real-time
3. Findings appear as they are discovered, sorted by severity
4. Export a full HTML report when the scan completes

---

## Roadmap

- [x] Phase 1 — Single domain scan, all 5 modules, React frontend, HTML report
- [ ] Phase 2 — TLD sweep (`.go.id` namespace), Celery parallel scanning, PDF report, CVSS-lite scoring
- [ ] Phase 3 — Persistent dashboard, scan history, bulk CSV upload, BSSN webhook
- [ ] Phase 4 — LLM analysis layer (local Qwen2-VL + IndoBERT embeddings) for 0-day injection detection

---

## Who This Is For

- **BSSN** (Badan Siber dan Sandi Negara) analysts
- Government IT teams doing self-assessment
- Investigative journalists covering judi online infiltration
- CTI / blue team analysts
- Academic security researchers

---

## Disclaimer

Pantauin performs **passive, non-intrusive scans only**. All HTTP probing is GET-only with no payload injection. It is a detection and evidence tool, not a penetration testing framework. Use only on domains you are authorized to scan.

---

## License

MIT

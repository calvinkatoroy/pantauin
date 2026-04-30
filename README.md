# PantauInd - Research Pipeline

![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat&logo=python&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-async-2ead33?style=flat&logo=playwright&logoColor=white)
![Statsmodels](https://img.shields.io/badge/Statsmodels-Logit-150458?style=flat)
![Research](https://img.shields.io/badge/Research-Data%20Collection-blueviolet?style=flat)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat)

> 5-stage CLI pipeline for national-scale empirical study of gambling SEO injection on `.go.id` domains.

This branch hosts the **research CLI** for an empirical study on gambling SEO injection in Indonesian government websites. The companion web scanner tool (FastAPI + React) lives on the [`main`](https://github.com/calvinkatoroy/pantauin/tree/main) and [`web-tool`](https://github.com/calvinkatoroy/pantauin/tree/web-tool) branches and is intentionally absent here. This branch is CSV-first, no database, no web UI.

---

## Research Title

**Attack Surface Profiling of Gambling-Injected Indonesian Government Websites Using Passive Web Reconnaissance: A National-Scale Empirical Study**

Status: data collection in progress (April 2026).

## The Gap

Prior work on gambling SEO injection in Indonesia focuses on detection - finding infected domains using dork queries and keyword matching. Meanwhile, attack surface measurement studies (Vasek 2016, Harry 2025, Kovacevic 2022) have shown that vulnerability characteristics like outdated CMS, missing security headers, and exposed admin panels correlate with compromise - but none have been applied to Indonesian government domains or to gambling injection specifically. This project bridges both streams.

## Research Questions

1. **RQ1:** What is the prevalence and distribution of gambling SEO injection across `.go.id` domains at national scale?
2. **RQ2:** What are the attack surface characteristics (security headers, exposed paths, CMS, version disclosure) of infected vs. clean domains?
3. **RQ3:** Which vulnerability features correlate significantly with gambling SEO injection status?

## Literature Gap

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

---

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

Key decisions: httpx + BS4 for bulk speed (not Playwright for 50k domains), Playwright only for the ~5% suspected, statsmodels for regression (thesis needs p-values and 95% CI, not sklearn), all domains profiled (infected + clean) for a proper control group. `data/` is gitignored - no domain lists committed.

## Statistical Plan

- Chi-square test per vulnerability feature (Bonferroni corrected)
- Fisher's exact fallback when expected cell < 5
- Logistic regression: odds ratio, 95% CI, p-value, pseudo-R-squared, AIC
- VIF check for multicollinearity
- Hosmer-Lemeshow goodness-of-fit

---

## Quick Start

```bash
git clone -b research-pipeline https://github.com/calvinkatoroy/pantauin.git
cd pantauin

python -m venv .venv
source .venv/bin/activate  # or: .venv\Scripts\activate on Windows
pip install -r research/requirements.txt
playwright install chromium

# Set CT enumeration credentials (each is independently optional)
export CERTSPOTTER_API_KEY=...
export CENSYS_API_ID=...
export CENSYS_API_SECRET=...

# Dry-run validates the pipeline end to end on a tiny sample
python -m research.cli run-all --dry-run

# Full namespace run (multi-hour)
python -m research.cli run-all
```

Individual stages can be run independently - see `research/README.md` for stage-by-stage usage.

---

## Repository Structure

```
research/
├── README.md             Pipeline usage docs
├── cli.py                CLI entrypoint
├── config.py             Tier A/B/C keyword lists + regex + thresholds
├── requirements.txt      Pinned Python deps
└── pipeline/
    ├── enumerate.py      Multi-source CT enumeration
    ├── detect.py         Bulk httpx + BS4 keyword scan
    ├── confirm.py        Playwright deep verification
    ├── surface.py        Passive vuln surface profiling
    └── analysis.py       Chi-square + logistic regression
```

---

## Ethics

Passive recon only. All HTTP probing is GET-only. No payload injection. No active exploitation. Evidence stored locally, never uploaded to third-party services. SHA256 hashing for chain-of-custody. Aggregate statistics and anonymized data will be published; raw infected domain lists will not. Responsible disclosure to BSSN before any public domain-level findings.

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

"""
Step 5 - Statistical Analysis

Inputs:
  data/processed/attack_surface.csv  - all domains with passive attack surface features
  data/processed/confirmed.csv       - Playwright-confirmed infection status

Outputs:
  data/tables/descriptive.{csv,tex}           - feature prevalence by infection status
  data/tables/chisquare.{csv,tex}             - chi-square + Cramer's V + Bonferroni
  data/tables/logistic_regression.{csv,tex}   - odds ratios, 95% CI, p-values, VIF
  data/tables/vif.{csv,tex}                   - variance inflation factors
  data/figures/feature_prevalence.png         - grouped horizontal bar chart
  data/figures/odds_ratio_forest.png          - forest plot with 95% CI
  data/figures/infection_distribution.png     - infection rate overview (by TLD)
  data/figures/cms_distribution.png           - CMS type vs infection status (stacked bar)

Statistical approach:
  - Outcome variable: infected (bool) = True if confirmed_infected == True
  - Predictor variables: BINARY_FEATURES from attack_surface.csv
  - Per-feature test: chi-square (Fisher's exact when expected cell < 5)
  - Multiple comparison correction: Bonferroni (alpha / n_tests)
  - Effect size: Cramer's V for chi-square results
  - Joint model: statsmodels Logit -> OR, 95% CI (profile likelihood), p-value
  - Multicollinearity check: VIF > VIF_THRESHOLD flagged in output

All figures: 300 DPI, seaborn whitegrid style, white background (print-safe).
LaTeX tables: paste-ready with \\caption and \\label.
"""

import logging
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import chi2_contingency, fisher_exact

import research.config as cfg

log = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# Apply seaborn style globally for all figures
sns.set_style("whitegrid")
sns.set_context("paper", font_scale=1.2)

PALETTE = {"Infected": "#d62728", "Clean": "#1f77b4"}  # standard red/blue


# ---------------------------------------------------------------------------
# Data loading + feature derivation
# ---------------------------------------------------------------------------

def _load_data() -> pd.DataFrame:
    """
    Load and merge attack_surface.csv with confirmed.csv.

    The merge is a LEFT JOIN on attack_surface: every domain that was profiled
    gets a row.  The `infected` column is True only for domains that appear in
    confirmed.csv with confirmed_infected == True.

    Returns:
        DataFrame with all attack surface columns plus `infected` (bool),
        `tld` (str), and derived CMS boolean columns.

    Raises:
        FileNotFoundError: If either input CSV is missing.
    """
    if not cfg.ATTACK_SURFACE_CSV.exists():
        raise FileNotFoundError(f"{cfg.ATTACK_SURFACE_CSV} - run `surface` first.")
    if not cfg.CONFIRMED_CSV.exists():
        raise FileNotFoundError(f"{cfg.CONFIRMED_CSV} - run `confirm` first.")

    surf = pd.read_csv(cfg.ATTACK_SURFACE_CSV, dtype=str)
    conf = pd.read_csv(cfg.CONFIRMED_CSV, dtype=str)

    # Confirmed-positive domain set
    conf_positive = set(
        conf.loc[
            conf["confirmed_infected"].str.lower() == "true",
            "domain",
        ].dropna()
    )
    log.info("Confirmed-positive domains in confirmed.csv: %d", len(conf_positive))

    surf["infected"] = surf["domain"].isin(conf_positive)

    # Coerce boolean columns (stored as 'True'/'False' strings)
    for col in cfg.BINARY_FEATURES:
        if col in surf.columns:
            surf[col] = surf[col].str.lower().map({"true": True, "false": False}).fillna(False)
        elif col == "cms_wordpress":
            surf[col] = surf["cms"].str.lower() == "wordpress"
        elif col == "cms_joomla":
            surf[col] = surf["cms"].str.lower() == "joomla"
        elif col == "cms_drupal":
            surf[col] = surf["cms"].str.lower() == "drupal"
        else:
            surf[col] = False

    # Bring in TLD from domains.csv if available (for infection_distribution figure)
    if cfg.DOMAINS_CSV.exists():
        try:
            tld_map = pd.read_csv(cfg.DOMAINS_CSV, dtype=str).set_index("domain")["tld"]
            surf["tld"] = surf["domain"].map(tld_map).fillna("unknown")
        except Exception:
            surf["tld"] = "unknown"
    else:
        surf["tld"] = "unknown"

    n_inf = int(surf["infected"].sum())
    n_tot = len(surf)
    log.info(
        "Dataset ready: n=%d | infected=%d (%.1f%%) | clean=%d",
        n_tot, n_inf, 100 * n_inf / n_tot if n_tot else 0, n_tot - n_inf,
    )
    return surf


# ---------------------------------------------------------------------------
# Table 1 - Descriptive statistics
# ---------------------------------------------------------------------------

def _descriptive_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a feature prevalence table split by infection status.

    Args:
        df: Merged DataFrame with `infected` bool column.

    Returns:
        DataFrame with columns: Feature, Infected (n=X), Clean (n=Y), Total (n=Z).
    """
    infected = df[df["infected"]]
    clean    = df[~df["infected"]]
    ni, nc, nt = len(infected), len(clean), len(df)

    rows = []
    for feat in cfg.BINARY_FEATURES:
        if feat not in df.columns:
            continue
        n_inf_feat = int(infected[feat].sum())
        n_cln_feat = int(clean[feat].sum())
        n_tot_feat = int(df[feat].sum())
        rows.append({
            "Feature":                       cfg.FEATURE_LABELS.get(feat, feat),
            f"Infected (n={ni})":            f"{n_inf_feat} ({100*n_inf_feat/ni:.1f}%)" if ni else "-",
            f"Clean (n={nc})":               f"{n_cln_feat} ({100*n_cln_feat/nc:.1f}%)" if nc else "-",
            f"Total (n={nt})":               f"{n_tot_feat} ({100*n_tot_feat/nt:.1f}%)" if nt else "-",
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Table 2 - Chi-square + Bonferroni
# ---------------------------------------------------------------------------

def _chisquare_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Run per-feature chi-square tests (Fisher's exact for small cells).

    Applies Bonferroni correction across all tests.
    Sorts results by p-value ascending.

    Args:
        df: DataFrame with `infected` bool column and BINARY_FEATURES.

    Returns:
        DataFrame with chi-square results per feature.
    """
    rows = []
    for feat in cfg.BINARY_FEATURES:
        if feat not in df.columns:
            continue

        ct = pd.crosstab(df[feat], df["infected"])
        if ct.shape != (2, 2):
            continue  # degenerate: all same value

        n = int(ct.values.sum())

        # Minimum expected cell count (determines test choice)
        row_sums = ct.values.sum(axis=1, keepdims=True)
        col_sums = ct.values.sum(axis=0, keepdims=True)
        expected = row_sums * col_sums / n
        min_exp  = expected.min()

        if min_exp < 5:
            _, pval = fisher_exact(ct.values)
            chi2_val, test_used = float("nan"), "Fisher"
        else:
            chi2_val, pval, _, _ = chi2_contingency(ct.values, correction=False)
            test_used = "Chi-square"

        # Cramer's V effect size
        if not np.isnan(chi2_val):
            cramers_v = np.sqrt(chi2_val / (n * min(ct.shape[0] - 1, ct.shape[1] - 1)))
        else:
            cramers_v = float("nan")

        rows.append({
            "Feature":    cfg.FEATURE_LABELS.get(feat, feat),
            "_feat":      feat,        # internal, dropped before output
            "Test":       test_used,
            "Chi2":       round(chi2_val, 4) if not np.isnan(chi2_val) else "-",
            "p-value":    pval,
            "Cramer's V": round(cramers_v, 4) if not np.isnan(cramers_v) else "-",
        })

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows).sort_values("p-value").reset_index(drop=True)

    # Bonferroni correction
    n_tests = len(result)
    bonf_alpha = cfg.ALPHA / n_tests
    result["Sig (alpha=.05)"]           = result["p-value"].apply(lambda p: "yes" if p < cfg.ALPHA else "no")
    result["Sig (Bonferroni)"]          = result["p-value"].apply(lambda p: "yes" if p < bonf_alpha else "no")
    result["p-value"]                   = result["p-value"].apply(lambda p: f"{p:.6f}")
    result["Bonferroni alpha"]          = f"{bonf_alpha:.6f}"

    return result.drop(columns=["_feat"])


# ---------------------------------------------------------------------------
# Table 3 - Logistic regression + VIF
# ---------------------------------------------------------------------------

def _logistic_and_vif(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Fit a logistic regression model and compute VIF for each predictor.

    Args:
        df: DataFrame with `infected` bool column and BINARY_FEATURES.

    Returns:
        Tuple of (logistic_results_df, vif_df).
        Both DataFrames are empty if statsmodels is unavailable or fitting fails.
    """
    try:
        import statsmodels.api as sm
        from statsmodels.stats.outliers_influence import variance_inflation_factor
    except ImportError:
        log.error("statsmodels not installed - skipping logistic regression + VIF")
        return pd.DataFrame(), pd.DataFrame()

    # Use only features present and with non-zero variance
    features = [
        f for f in cfg.BINARY_FEATURES
        if f in df.columns and df[f].astype(float).std() > 0
    ]
    if not features:
        log.warning("No variable features for logistic regression")
        return pd.DataFrame(), pd.DataFrame()

    X = df[features].astype(float)
    y = df["infected"].astype(int)

    # --- VIF (computed before adding constant) ---
    vif_rows = []
    for i, feat in enumerate(features):
        try:
            vif = variance_inflation_factor(X.values, i)
        except Exception:
            vif = float("nan")
        vif_rows.append({
            "Feature": cfg.FEATURE_LABELS.get(feat, feat),
            "VIF":     round(vif, 3),
            "High VIF (>10)": "YES - multicollinear" if vif > cfg.VIF_THRESHOLD else "no",
        })
    vif_df = pd.DataFrame(vif_rows).sort_values("VIF", ascending=False)

    high_vif = [r["Feature"] for r in vif_rows if r["High VIF (>10)"].startswith("YES")]
    if high_vif:
        log.warning("Multicollinearity detected (VIF > %.1f): %s", cfg.VIF_THRESHOLD, high_vif)

    # --- Logistic regression ---
    X_const = sm.add_constant(X)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = sm.Logit(y, X_const).fit(disp=0, maxiter=300)
    except Exception as exc:
        log.error("Logistic regression failed: %s", exc)
        return pd.DataFrame(), vif_df

    log.info(
        "Logistic regression: McFadden R2=%.3f  AIC=%.1f  n=%d",
        model.prsquared, model.aic, int(model.nobs),
    )

    ci = model.conf_int()
    lr_rows = []
    for feat in features:
        coef   = model.params.get(feat, float("nan"))
        pval   = model.pvalues.get(feat, float("nan"))
        ci_lo  = ci.loc[feat, 0] if feat in ci.index else float("nan")
        ci_hi  = ci.loc[feat, 1] if feat in ci.index else float("nan")

        lr_rows.append({
            "Feature":         cfg.FEATURE_LABELS.get(feat, feat),
            "Coef (log-OR)":   round(coef, 4),
            "Odds Ratio":      round(np.exp(coef), 4),
            "OR 95% CI Low":   round(np.exp(ci_lo), 4),
            "OR 95% CI High":  round(np.exp(ci_hi), 4),
            "p-value":         f"{pval:.6f}",
            "Significant":     "yes" if pval < cfg.ALPHA else "no",
        })

    lr_df = pd.DataFrame(lr_rows).sort_values("p-value")
    return lr_df, vif_df


# ---------------------------------------------------------------------------
# LaTeX export helper
# ---------------------------------------------------------------------------

def _to_latex(df: pd.DataFrame, caption: str, label: str) -> str:
    """
    Convert a DataFrame to a paste-ready LaTeX table string.

    Args:
        df:      DataFrame to convert.
        caption: Table caption text.
        label:   LaTeX \\label key (e.g. "tab:chisquare").

    Returns:
        LaTeX table string including \\begin{table} ... \\end{table} wrapper.
    """
    col_fmt = "l" + "r" * (len(df.columns) - 1)
    body = df.to_latex(index=False, escape=True, column_format=col_fmt)
    return (
        "\\begin{table}[ht]\n"
        "\\centering\n"
        f"\\caption{{{caption}}}\n"
        f"\\label{{{label}}}\n"
        + body
        + "\\end{table}\n"
    )


def _save_table(df: pd.DataFrame, stem: str, caption: str, label: str) -> None:
    """Save DataFrame as both .csv and .tex."""
    csv_path = cfg.DATA_TABLES / f"{stem}.csv"
    tex_path = cfg.DATA_TABLES / f"{stem}.tex"
    df.to_csv(csv_path, index=False)
    tex_path.write_text(_to_latex(df, caption, label), encoding="utf-8")
    log.info("Table saved -> %s  %s", csv_path.name, tex_path.name)


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def _plot_feature_prevalence(df: pd.DataFrame) -> None:
    """
    Grouped horizontal bar chart showing feature prevalence for infected vs clean domains.

    Args:
        df: DataFrame with `infected` bool column and BINARY_FEATURES.
    """
    infected = df[df["infected"]]
    clean    = df[~df["infected"]]

    feats   = [f for f in cfg.BINARY_FEATURES if f in df.columns]
    labels  = [cfg.FEATURE_LABELS.get(f, f) for f in feats]
    inf_pct = [infected[f].mean() * 100 for f in feats]
    cln_pct = [clean[f].mean() * 100 for f in feats]

    y = np.arange(len(feats))
    h = 0.35

    fig, ax = plt.subplots(figsize=(11, max(6, len(feats) * 0.6)))
    fig.patch.set_facecolor("white")

    bars_inf = ax.barh(y + h / 2, inf_pct, h, label="Infected", color=PALETTE["Infected"], alpha=0.85)
    bars_cln = ax.barh(y - h / 2, cln_pct, h, label="Clean",    color=PALETTE["Clean"],    alpha=0.85)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlabel("Domains with feature (%)", fontsize=11)
    ax.set_title(
        "Attack Surface Feature Prevalence: Infected vs Clean .go.id / .ac.id Domains",
        fontsize=12, fontweight="bold", pad=14,
    )
    ax.legend(loc="lower right", fontsize=10)
    ax.set_xlim(0, 110)
    ax.xaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    # Value labels on bars > 2%
    for bar, color in [(bars_inf, PALETTE["Infected"]), (bars_cln, PALETTE["Clean"])]:
        for b in bar:
            w = b.get_width()
            if w > 2:
                ax.text(
                    w + 0.5, b.get_y() + b.get_height() / 2,
                    f"{w:.0f}%", va="center", fontsize=7, color=color,
                )

    plt.tight_layout()
    _save_figure("feature_prevalence.png")


def _plot_odds_ratio_forest(lr_df: pd.DataFrame) -> None:
    """
    Forest plot of odds ratios with 95% CI from logistic regression.

    Args:
        lr_df: Logistic regression results DataFrame.
    """
    if lr_df.empty:
        return

    df = lr_df.copy().reset_index(drop=True)
    n = len(df)
    y = np.arange(n)

    fig, ax = plt.subplots(figsize=(9, max(5, n * 0.65)))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    for i, row in df.iterrows():
        sig   = row["Significant"] == "yes"
        color = PALETTE["Infected"] if sig else "#aaaaaa"
        ci_lo = float(row["OR 95% CI Low"])
        ci_hi = float(row["OR 95% CI High"])
        or_   = float(row["Odds Ratio"])
        # Clip extreme CI bounds for log-scale readability
        ci_lo = max(ci_lo, 1e-3)
        ci_hi = min(ci_hi, 1e3)
        ax.plot([ci_lo, ci_hi], [i, i], color=color, linewidth=2, zorder=2)
        ax.scatter(or_, i, color=color, s=60, zorder=3)

    ax.axvline(1.0, color="black", linestyle="--", linewidth=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(df["Feature"], fontsize=10)
    ax.set_xlabel("Odds Ratio (95% CI, log scale)", fontsize=11)
    ax.set_title(
        "Logistic Regression: Odds Ratios for Gambling Injection\n"
        "(red = significant at p < 0.05, grey = not significant)",
        fontsize=12, fontweight="bold", pad=12,
    )
    ax.set_xscale("log")
    ax.xaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)

    legend_handles = [
        mpatches.Patch(color=PALETTE["Infected"], label="Significant (p < 0.05)"),
        mpatches.Patch(color="#aaaaaa",            label="Not significant"),
    ]
    ax.legend(handles=legend_handles, loc="lower right", fontsize=10)

    plt.tight_layout()
    _save_figure("odds_ratio_forest.png")


def _plot_infection_distribution(df: pd.DataFrame) -> None:
    """
    Bar chart showing infection rates by TLD (go.id vs ac.id) and overall.

    Args:
        df: DataFrame with `infected` bool and `tld` columns.
    """
    groups = {"Overall": df}
    for tld in df["tld"].unique():
        if tld and tld != "unknown":
            groups[f".{tld}"] = df[df["tld"] == tld]

    names, rates, counts = [], [], []
    for name, grp in groups.items():
        if len(grp) == 0:
            continue
        rate = 100 * grp["infected"].mean()
        names.append(name)
        rates.append(rate)
        counts.append(len(grp))

    fig, ax = plt.subplots(figsize=(max(5, len(names) * 1.8), 5))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    colors = [PALETTE["Infected"] if n == "Overall" else "#5588aa" for n in names]
    bars = ax.bar(names, rates, color=colors, width=0.5, edgecolor="white")

    for bar, count in zip(bars, counts):
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            h + 0.3,
            f"{h:.1f}%\n(n={count:,})",
            ha="center", va="bottom", fontsize=10,
        )

    ax.set_ylabel("Infection Rate (%)", fontsize=11)
    ax.set_title(
        "Gambling SEO Injection Prevalence by Domain Group",
        fontsize=12, fontweight="bold", pad=12,
    )
    ax.set_ylim(0, max(rates) * 1.25 + 1)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    plt.tight_layout()
    _save_figure("infection_distribution.png")


def _plot_cms_distribution(df: pd.DataFrame) -> None:
    """
    Stacked bar chart: CMS type vs infection status (infected/clean counts).

    Args:
        df: DataFrame with `infected` bool and `cms` columns.
    """
    if "cms" not in df.columns:
        return

    cms_order = ["wordpress", "joomla", "drupal", "unknown"]
    infected  = df[df["infected"]]
    clean     = df[~df["infected"]]

    inf_counts = [int((infected["cms"].str.lower() == c).sum()) for c in cms_order]
    cln_counts = [int((clean["cms"].str.lower() == c).sum()) for c in cms_order]
    labels     = ["WordPress", "Joomla", "Drupal", "Unknown CMS"]

    x = np.arange(len(cms_order))
    w = 0.5

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    b_inf = ax.bar(x, inf_counts, w, label="Infected", color=PALETTE["Infected"], alpha=0.85)
    b_cln = ax.bar(x, cln_counts, w, bottom=inf_counts, label="Clean", color=PALETTE["Clean"], alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylabel("Domain count", fontsize=11)
    ax.set_title(
        "CMS Distribution: Infected vs Clean Domains",
        fontsize=12, fontweight="bold", pad=12,
    )
    ax.legend(fontsize=10)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    plt.tight_layout()
    _save_figure("cms_distribution.png")


def _save_figure(filename: str) -> None:
    """Save current matplotlib figure at 300 DPI."""
    path = cfg.DATA_FIGURES / filename
    plt.savefig(str(path), dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()
    log.info("Figure saved -> %s", path.name)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_analysis() -> None:
    """
    Execute all statistical analyses and write tables + figures.

    Steps:
      1. Load and merge data
      2. Descriptive statistics table
      3. Chi-square tests with Bonferroni correction
      4. Logistic regression + VIF
      5. Four publication-quality figures
    """
    df = _load_data()

    n_inf = int(df["infected"].sum())
    n_tot = len(df)

    if n_inf == 0:
        log.warning(
            "Zero confirmed-positive domains in dataset.  "
            "Chi-square and logistic regression require at least one positive case.  "
            "Run the `confirm` step first, or check confirmed.csv."
        )
        return

    log.info("Analysis: n=%d total | infected=%d | clean=%d", n_tot, n_inf, n_tot - n_inf)

    # --- Table 1: Descriptive ---
    desc = _descriptive_table(df)
    _save_table(
        desc,
        "descriptive",
        "Attack Surface Feature Prevalence by Infection Status",
        "tab:descriptive",
    )

    # --- Table 2: Chi-square + Bonferroni ---
    chi = _chisquare_table(df)
    if not chi.empty:
        _save_table(
            chi,
            "chisquare",
            "Chi-square Tests: Attack Surface Features vs Infection Status "
            "(Bonferroni corrected)",
            "tab:chisquare",
        )
        sig_bonf = chi[chi["Sig (Bonferroni)"] == "yes"]
        if not sig_bonf.empty:
            log.info(
                "Features significant after Bonferroni correction (n=%d):", len(sig_bonf)
            )
            for _, row in sig_bonf.iterrows():
                log.info("  %s  p=%s  V=%s", row["Feature"], row["p-value"], row["Cramer's V"])
        else:
            log.info("No features survive Bonferroni correction (alpha/n=%.6f)", cfg.ALPHA / len(chi))

    # --- Table 3: Logistic regression + VIF ---
    lr_df, vif_df = _logistic_and_vif(df)
    if not lr_df.empty:
        _save_table(
            lr_df,
            "logistic_regression",
            "Logistic Regression Predictors of Gambling SEO Injection "
            "(Odds Ratios with 95\\% CI)",
            "tab:logistic",
        )
    if not vif_df.empty:
        _save_table(
            vif_df,
            "vif",
            "Variance Inflation Factors (VIF) for Logistic Regression Predictors",
            "tab:vif",
        )

    # --- Figures ---
    _plot_feature_prevalence(df)
    _plot_infection_distribution(df)
    _plot_cms_distribution(df)
    if not lr_df.empty:
        _plot_odds_ratio_forest(lr_df)

    log.info(
        "Analysis complete.\n  Tables: %s\n  Figures: %s",
        cfg.DATA_TABLES, cfg.DATA_FIGURES,
    )

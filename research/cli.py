"""
PantauInd Research Pipeline - CLI entry point

Run from the repo root:
    python -m research.cli [OPTIONS] COMMAND

Global options (apply to all commands):
    --output-dir PATH   Override default data/ directory (or set RESEARCH_DATA_DIR env var)
    --dry-run           Process only the first 50 domains (for testing)

Commands:
    enumerate   Step 1 - crt.sh CT logs -> data/raw/domains.csv
    detect      Step 2 - httpx+BS4 bulk scan -> data/interim/suspected.csv  [checkpoint/resume]
    confirm     Step 3 - Playwright deep confirm -> data/processed/confirmed.csv  [checkpoint/resume]
    surface     Step 4 - passive attack surface -> data/processed/attack_surface.csv  [checkpoint/resume]
    analyse     Step 5 - statistics -> data/tables/ + data/figures/
    run-all     Run all five steps in sequence

Examples:
    # Dry run (50 domains) to verify pipeline works
    python -m research.cli --dry-run run-all

    # Full pipeline with custom output directory
    python -m research.cli --output-dir /mnt/data/thesis run-all

    # Resume a killed detection run
    python -m research.cli detect

    # Re-fetch domain list (force overwrite)
    python -m research.cli enumerate --force
"""

# IMPORTANT: No research.* imports at module level.
# All pipeline imports are deferred inside command functions so that
# --output-dir can set RESEARCH_DATA_DIR *before* research.config is imported.
import os
import sys
import asyncio
import logging

import click

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("research")

DRY_RUN_LIMIT = 50


# ---------------------------------------------------------------------------
# Global group: handles --output-dir and --dry-run before any command runs
# ---------------------------------------------------------------------------

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--output-dir",
    envvar="RESEARCH_DATA_DIR",
    default=None,
    metavar="PATH",
    help="Override data directory (default: research/data/). "
         "Also reads RESEARCH_DATA_DIR env var.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help=f"Process only the first {DRY_RUN_LIMIT} domains (for testing).",
)
@click.pass_context
def cli(ctx: click.Context, output_dir: str | None, dry_run: bool) -> None:
    """PantauInd Research Pipeline - Gambling SEO injection study on .go.id domains."""
    ctx.ensure_object(dict)
    ctx.obj["dry_run"] = dry_run
    ctx.obj["limit"] = DRY_RUN_LIMIT if dry_run else 0

    # Set env var BEFORE any research.* module is imported (they are lazy).
    if output_dir:
        os.environ["RESEARCH_DATA_DIR"] = str(output_dir)
        log.info("Data directory: %s", output_dir)

    if dry_run:
        log.info("DRY RUN mode: processing first %d domains only", DRY_RUN_LIMIT)


# ---------------------------------------------------------------------------
# Step 1: enumerate
# ---------------------------------------------------------------------------

@cli.command("enumerate")
@click.option("--force", is_flag=True, help="Re-fetch even if domains.csv already exists.")
@click.pass_context
def cmd_enumerate(ctx: click.Context, force: bool) -> None:
    """Step 1: Enumerate .go.id / .ac.id domains via crt.sh CT logs."""
    from research.pipeline.enumerate import enumerate_domains

    limit = ctx.obj["limit"]
    try:
        asyncio.run(enumerate_domains(limit=limit, force=force))
    except Exception as exc:
        log.error("enumerate failed: %s", exc)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Step 2: detect
# ---------------------------------------------------------------------------

@cli.command("detect")
@click.pass_context
def cmd_detect(ctx: click.Context) -> None:
    """Step 2: Bulk gambling content detection (httpx + BeautifulSoup). Resumes from checkpoint."""
    from research.pipeline.detect import detect_suspected

    limit = ctx.obj["limit"]
    try:
        asyncio.run(detect_suspected(limit=limit))
    except FileNotFoundError as exc:
        log.error("%s", exc)
        sys.exit(1)
    except Exception as exc:
        log.error("detect failed: %s", exc)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Step 3: confirm
# ---------------------------------------------------------------------------

@cli.command("confirm")
@click.pass_context
def cmd_confirm(ctx: click.Context) -> None:
    """Step 3: Deep confirmation via Playwright (JS-rendered). Resumes from checkpoint."""
    from research.pipeline.confirm import confirm_domains

    limit = ctx.obj["limit"]
    try:
        asyncio.run(confirm_domains(limit=limit))
    except FileNotFoundError as exc:
        log.error("%s", exc)
        sys.exit(1)
    except Exception as exc:
        log.error("confirm failed: %s", exc)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Step 4: surface
# ---------------------------------------------------------------------------

@cli.command("surface")
@click.pass_context
def cmd_surface(ctx: click.Context) -> None:
    """Step 4: Passive attack surface profiling (httpx). Resumes from checkpoint."""
    from research.pipeline.surface import profile_attack_surface

    limit = ctx.obj["limit"]
    try:
        asyncio.run(profile_attack_surface(limit=limit))
    except FileNotFoundError as exc:
        log.error("%s", exc)
        sys.exit(1)
    except Exception as exc:
        log.error("surface failed: %s", exc)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Step 5: analyse
# ---------------------------------------------------------------------------

@cli.command("analyse")
@click.pass_context
def cmd_analyse(ctx: click.Context) -> None:
    """Step 5: Statistical analysis - chi-square, logistic regression, figures."""
    from research.pipeline.analysis import run_analysis

    try:
        run_analysis()
    except FileNotFoundError as exc:
        log.error("%s", exc)
        sys.exit(1)
    except Exception as exc:
        log.error("analyse failed: %s", exc)
        sys.exit(1)


# ---------------------------------------------------------------------------
# run-all: sequential pipeline + final summary
# ---------------------------------------------------------------------------

@cli.command("run-all")
@click.option("--force-enumerate", is_flag=True, help="Re-fetch domains even if domains.csv exists.")
@click.pass_context
def cmd_run_all(ctx: click.Context, force_enumerate: bool) -> None:
    """Run all five steps in sequence, then print a research summary."""
    from research.pipeline.enumerate import enumerate_domains
    from research.pipeline.detect import detect_suspected
    from research.pipeline.confirm import confirm_domains
    from research.pipeline.surface import profile_attack_surface
    from research.pipeline.analysis import run_analysis
    import research.config as cfg

    limit = ctx.obj["limit"]

    def _banner(step: str) -> None:
        click.echo(click.style(f"\n{'='*60}", fg="cyan"))
        click.echo(click.style(f"  {step}", fg="cyan", bold=True))
        click.echo(click.style(f"{'='*60}", fg="cyan"))

    try:
        _banner("STEP 1/5  Domain Enumeration (crt.sh)")
        asyncio.run(enumerate_domains(limit=limit, force=force_enumerate))

        _banner("STEP 2/5  Bulk Detection (httpx + BeautifulSoup)")
        asyncio.run(detect_suspected(limit=limit))

        _banner("STEP 3/5  Deep Confirmation (Playwright)")
        asyncio.run(confirm_domains(limit=limit))

        _banner("STEP 4/5  Attack Surface Profiling (httpx)")
        asyncio.run(profile_attack_surface(limit=limit))

        _banner("STEP 5/5  Statistical Analysis")
        run_analysis()

    except KeyboardInterrupt:
        click.echo("\nInterrupted. Checkpoints saved - resume with the same command.")
        sys.exit(0)
    except FileNotFoundError as exc:
        log.error("%s", exc)
        sys.exit(1)
    except Exception as exc:
        log.error("Pipeline failed: %s", exc)
        sys.exit(1)

    # --- Final summary ---
    _print_summary(cfg)


def _print_summary(cfg) -> None:
    """Read output CSVs and print a formatted research summary."""
    import pandas as pd

    def _count(path, col=None, val=None):
        try:
            df = pd.read_csv(path)
            if col and val is not None:
                return int((df[col].astype(str).str.lower() == str(val).lower()).sum())
            return len(df)
        except Exception:
            return 0

    n_domains   = _count(cfg.DOMAINS_CSV)
    n_scanned   = _count(cfg.SUSPECTED_CSV)
    n_suspected = _count(cfg.SUSPECTED_CSV, "keyword_hits", None)
    try:
        sus_df = pd.read_csv(cfg.SUSPECTED_CSV)
        n_suspected = int((sus_df["keyword_hits"].fillna(0).astype(int) > 0).sum())
    except Exception:
        n_suspected = 0
    n_confirmed = _count(cfg.CONFIRMED_CSV, "confirmed_infected", "true")
    n_profiled  = _count(cfg.ATTACK_SURFACE_CSV)

    sus_pct = f"{100*n_suspected/n_scanned:.1f}%" if n_scanned else "N/A"
    con_pct = f"{100*n_confirmed/n_scanned:.1f}%" if n_scanned else "N/A"

    click.echo(click.style("\n" + "=" * 47, fg="green", bold=True))
    click.echo(click.style("  PANTAUIND RESEARCH PIPELINE - SUMMARY", fg="green", bold=True))
    click.echo(click.style("=" * 47, fg="green", bold=True))
    click.echo(f"  Domains enumerated:    {n_domains:>8,}")
    click.echo(f"  Domains scanned:       {n_scanned:>8,}")
    click.echo(f"  Suspected infected:    {n_suspected:>8,}  ({sus_pct})")
    click.echo(f"  Confirmed infected:    {n_confirmed:>8,}  ({con_pct})")
    click.echo(f"  Domains profiled:      {n_profiled:>8,}")
    click.echo(f"  Analysis outputs:      data/tables/  data/figures/")
    click.echo(click.style("=" * 47, fg="green", bold=True))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    try:
        cli(standalone_mode=False)
    except click.exceptions.Abort:
        click.echo("\nAborted. Checkpoints saved - resume with the same command.")
        sys.exit(0)
    except click.ClickException as exc:
        exc.show()
        sys.exit(exc.exit_code)
    except SystemExit:
        raise
    except Exception as exc:
        log.error("Unexpected error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()

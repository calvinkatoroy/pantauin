import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db
from app.models.scan import ScanJob

router = APIRouter()

WIB = timezone(timedelta(hours=7))

SEVERITY_COLORS = {
    "critical": "#ef4444",
    "high": "#f97316",
    "medium": "#eab308",
    "low": "#3b82f6",
    "info": "#6b7280",
}

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _render_report(job: ScanJob) -> str:
    findings = sorted(job.findings, key=lambda f: SEVERITY_ORDER.get(f.severity, 99))
    generated_at = datetime.now(WIB).strftime("%Y-%m-%d %H:%M:%S WIB")

    finding_rows = ""
    for f in findings:
        color = SEVERITY_COLORS.get(f.severity, "#6b7280")
        keywords = json.loads(f.detected_keywords) if f.detected_keywords else []
        links = json.loads(f.injected_links) if f.injected_links else []

        keywords_html = ""
        if keywords:
            keywords_html = "<p><strong>Detected keywords:</strong> " + escape(", ".join(keywords)) + "</p>"

        links_html = ""
        if links:
            links_html = "<p><strong>Injected links:</strong><br>" + "<br>".join(escape(l) for l in links[:5]) + "</p>"

        screenshot_html = ""
        if f.screenshot_path:
            screenshot_html = f"""
            <div style="margin-top:12px;">
                <img src="/evidence/{escape(f.screenshot_path)}"
                     alt="Evidence screenshot"
                     style="max-width:100%;border:1px solid #333;border-radius:4px;"
                     loading="lazy" />
                <p style="font-size:11px;color:#888;margin-top:4px;">
                    SHA256: {escape(f.screenshot_hash or '')}
                </p>
            </div>
            """

        finding_rows += f"""
        <div style="border:1px solid #2a2d35;border-radius:8px;padding:16px;margin-bottom:12px;background:#111318;">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                <span style="background:{color};color:#fff;font-size:11px;font-weight:700;
                             padding:2px 8px;border-radius:4px;text-transform:uppercase;">
                    {escape(f.severity)}
                </span>
                <span style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.05em;">
                    {escape(f.module)}
                </span>
                {f'<span style="font-size:11px;font-weight:600;color:{color};">CVSS-Lite: {f.cvss_score}</span>' if f.cvss_score is not None else ""}
            </div>
            <p style="font-weight:600;margin:0 0 4px;">{escape(f.title)}</p>
            <p style="font-size:12px;color:#9aa;">
                <a href="{escape(f.url)}" style="color:#e8c547;" target="_blank" rel="noopener">
                    {escape(f.url)}
                </a>
            </p>
            {f'<p style="font-size:13px;color:#ccc;margin-top:8px;">{escape(f.description or "")}</p>' if f.description else ""}
            {keywords_html}
            {links_html}
            {screenshot_html}
        </div>
        """

    critical_count = sum(1 for f in findings if f.severity == "critical")
    high_count = sum(1 for f in findings if f.severity == "high")
    medium_count = sum(1 for f in findings if f.severity == "medium")
    low_count = sum(1 for f in findings if f.severity == "low")
    info_count = sum(1 for f in findings if f.severity == "info")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>PantauInd Report - {escape(job.domain)}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{ background:#0a0c0f; color:#e2e8f0; font-family:'DM Sans',system-ui,sans-serif;
         margin:0; padding:24px; }}
  h1 {{ font-size:22px; font-weight:700; margin:0 0 4px; }}
  h2 {{ font-size:16px; font-weight:600; margin:24px 0 12px; border-bottom:1px solid #2a2d35;
        padding-bottom:8px; }}
  a {{ color:#e8c547; }}
  .meta {{ color:#888; font-size:13px; margin-bottom:24px; }}
  .summary {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:24px; }}
  .badge {{ padding:6px 14px; border-radius:6px; font-size:13px; font-weight:600; }}
</style>
</head>
<body>
<h1>PantauInd Security Report</h1>
<div class="meta">
  <strong>Target:</strong> {escape(job.domain)} &nbsp;|&nbsp;
  <strong>Status:</strong> {escape(job.status)} &nbsp;|&nbsp;
  <strong>Generated:</strong> {generated_at} &nbsp;|&nbsp;
  <strong>Scan ID:</strong> {escape(job.id)}
</div>

<h2>Summary</h2>
<div class="summary">
  <div class="badge" style="background:#7f1d1d;color:#fca5a5;">Critical: {critical_count}</div>
  <div class="badge" style="background:#7c2d12;color:#fdba74;">High: {high_count}</div>
  <div class="badge" style="background:#713f12;color:#fde047;">Medium: {medium_count}</div>
  <div class="badge" style="background:#1e3a5f;color:#93c5fd;">Low: {low_count}</div>
  <div class="badge" style="background:#1f2937;color:#9ca3af;">Info: {info_count}</div>
</div>

<h2>Findings ({len(findings)} total)</h2>
{finding_rows if finding_rows else '<p style="color:#666;">No findings recorded.</p>'}

<p style="margin-top:40px;font-size:11px;color:#444;text-align:center;">
  Generated by PantauInd - Indonesian Government &amp; Academic Website Security Scanner
</p>
</body>
</html>"""


def _render_pdf_html(job: ScanJob) -> str:
    """Print-optimised HTML for WeasyPrint - white background, black text."""
    findings = sorted(job.findings, key=lambda f: SEVERITY_ORDER.get(f.severity, 99))
    generated_at = datetime.now(WIB).strftime("%Y-%m-%d %H:%M:%S WIB")

    PRINT_COLORS = {
        "critical": {"bg": "#fef2f2", "border": "#ef4444", "text": "#991b1b"},
        "high":     {"bg": "#fff7ed", "border": "#f97316", "text": "#9a3412"},
        "medium":   {"bg": "#fefce8", "border": "#eab308", "text": "#854d0e"},
        "low":      {"bg": "#eff6ff", "border": "#3b82f6", "text": "#1e40af"},
        "info":     {"bg": "#f9fafb", "border": "#9ca3af", "text": "#374151"},
    }

    finding_rows = ""
    for f in findings:
        c = PRINT_COLORS.get(f.severity, PRINT_COLORS["info"])
        keywords = json.loads(f.detected_keywords) if f.detected_keywords else []
        links = json.loads(f.injected_links) if f.injected_links else []

        keywords_html = (
            f'<p class="detail"><strong>Keywords:</strong> {escape(", ".join(keywords))}</p>'
            if keywords else ""
        )
        links_html = (
            '<p class="detail"><strong>Injected links:</strong><br>'
            + "<br>".join(f'<code>{escape(l)}</code>' for l in links[:5])
            + "</p>"
        ) if links else ""
        screenshot_html = (
            f'<img src="/evidence/{escape(f.screenshot_path)}" class="screenshot" alt="Evidence"/>'
            f'<p class="hash">SHA256: {escape(f.screenshot_hash or "")}</p>'
        ) if f.screenshot_path else ""

        finding_rows += f"""
        <div class="finding" style="border-left:4px solid {c['border']};background:{c['bg']};">
            <div class="finding-header">
                <span class="badge" style="background:{c['border']};color:#fff;">{escape(f.severity.upper())}</span>
                <span class="module">{escape(f.module)}</span>
                {f'<span class="score" style="color:{c["border"]};">CVSS-Lite {f.cvss_score}</span>' if f.cvss_score is not None else ""}
            </div>
            <p class="finding-title">{escape(f.title)}</p>
            <p class="url"><a href="{escape(f.url)}">{escape(f.url)}</a></p>
            {f'<p class="desc">{escape(f.description or "")}</p>' if f.description else ""}
            {keywords_html}{links_html}{screenshot_html}
        </div>"""

    critical_c = sum(1 for f in findings if f.severity == "critical")
    high_c     = sum(1 for f in findings if f.severity == "high")
    medium_c   = sum(1 for f in findings if f.severity == "medium")
    low_c      = sum(1 for f in findings if f.severity == "low")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>PantauInd Report - {escape(job.domain)}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{ font-family: 'Liberation Sans', Arial, sans-serif; font-size: 13px;
         color: #111; background: #fff; margin: 0; padding: 32px; }}
  h1 {{ font-size: 20px; font-weight: 700; margin: 0 0 4px; }}
  h2 {{ font-size: 14px; font-weight: 600; margin: 24px 0 10px;
        border-bottom: 1px solid #e5e7eb; padding-bottom: 6px; color: #374151; }}
  .meta {{ color: #6b7280; font-size: 12px; margin-bottom: 20px; line-height: 1.6; }}
  .summary {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; }}
  .sum-card {{ padding: 8px 14px; border-radius: 6px; font-size: 12px; font-weight: 600;
               border: 1px solid #e5e7eb; }}
  .finding {{ border-radius: 6px; padding: 14px 16px; margin-bottom: 10px;
              page-break-inside: avoid; }}
  .finding-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }}
  .badge {{ font-size: 10px; font-weight: 700; padding: 2px 7px;
            border-radius: 3px; text-transform: uppercase; letter-spacing: .04em; }}
  .module {{ font-size: 10px; color: #6b7280; text-transform: uppercase; letter-spacing: .05em; }}
  .score  {{ font-size: 10px; font-weight: 600; }}
  .finding-title {{ font-weight: 600; margin: 0 0 3px; font-size: 13px; }}
  .url a {{ color: #1d4ed8; font-size: 11px; word-break: break-all; }}
  .desc {{ color: #4b5563; font-size: 12px; margin-top: 6px; }}
  .detail {{ color: #374151; font-size: 12px; margin-top: 5px; }}
  code {{ font-size: 11px; background: #f3f4f6; padding: 1px 4px; border-radius: 3px; }}
  .screenshot {{ max-width: 100%; border: 1px solid #d1d5db;
                 border-radius: 4px; margin-top: 10px; }}
  .hash {{ font-size: 10px; color: #9ca3af; margin-top: 3px; word-break: break-all; }}
  .footer {{ margin-top: 40px; font-size: 10px; color: #9ca3af; text-align: center;
             border-top: 1px solid #e5e7eb; padding-top: 12px; }}
  @page {{ margin: 20mm; }}
</style>
</head>
<body>
<h1>PantauInd Security Report</h1>
<div class="meta">
  <strong>Target:</strong> {escape(job.domain)}<br>
  <strong>Status:</strong> {escape(job.status)} &nbsp;|&nbsp;
  <strong>Scan ID:</strong> {escape(job.id)}<br>
  <strong>Generated:</strong> {generated_at}
</div>

<h2>Summary</h2>
<div class="summary">
  <div class="sum-card" style="background:#fef2f2;color:#991b1b;">Critical: {critical_c}</div>
  <div class="sum-card" style="background:#fff7ed;color:#9a3412;">High: {high_c}</div>
  <div class="sum-card" style="background:#fefce8;color:#854d0e;">Medium: {medium_c}</div>
  <div class="sum-card" style="background:#eff6ff;color:#1e40af;">Low: {low_c}</div>
  <div class="sum-card" style="background:#f9fafb;color:#374151;">Total: {len(findings)}</div>
</div>

<h2>Findings ({len(findings)} total)</h2>
{finding_rows if finding_rows else '<p style="color:#9ca3af;">No findings recorded.</p>'}

<div class="footer">Generated by PantauInd - Indonesian Government &amp; Academic Website Security Scanner</div>
</body>
</html>"""


def _weasyprint_sync(html: str) -> bytes:
    from weasyprint import HTML
    return HTML(string=html, base_url="/").write_pdf()


async def _generate_pdf(html: str) -> bytes:
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=1) as pool:
        return await loop.run_in_executor(pool, _weasyprint_sync, html)


@router.get("/scan/{scan_id}/report", response_class=HTMLResponse)
async def get_report(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    result = await db.execute(
        select(ScanJob)
        .where(ScanJob.id == scan_id)
        .options(selectinload(ScanJob.findings))
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Scan not found")

    html = _render_report(job)
    return HTMLResponse(content=html, headers={
        "Content-Disposition": f'attachment; filename="pantauind-{job.domain}-{job.id[:8]}.html"'
    })


@router.get("/scan/{scan_id}/report/pdf")
async def get_report_pdf(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    result = await db.execute(
        select(ScanJob)
        .where(ScanJob.id == scan_id)
        .options(selectinload(ScanJob.findings))
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Scan not found")

    html = _render_pdf_html(job)
    pdf_bytes = await _generate_pdf(html)
    filename = f"pantauind-{job.domain}-{job.id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

import json
from datetime import datetime, timezone, timedelta
from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
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
<title>Pantauin Report — {escape(job.domain)}</title>
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
<h1>Pantauin Security Report</h1>
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
  Generated by Pantauin — Indonesian Government &amp; Academic Website Security Scanner
</p>
</body>
</html>"""


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
        "Content-Disposition": f'attachment; filename="pantauin-{job.domain}-{job.id[:8]}.html"'
    })

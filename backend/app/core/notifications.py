"""
Email and Slack notifications for Critical findings.

Both channels are non-fatal - failure is logged but never propagates to
the scan pipeline. Fires alongside the existing WEBHOOK_URL mechanism.

Configuration:
  Email:  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_TO
  Slack:  SLACK_WEBHOOK_URL
"""
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _email_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from and settings.smtp_to)


def _slack_configured() -> bool:
    return bool(settings.slack_webhook_url)


async def _send_email(subject: str, html_body: str) -> None:
    """Send HTML email via SMTP with STARTTLS."""
    try:
        import aiosmtplib  # type: ignore

        recipients = [r.strip() for r in settings.smtp_to.split(",") if r.strip()]
        if not recipients:
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            start_tls=True,
        )
        logger.info("Notification email sent to %s", settings.smtp_to)
    except Exception as exc:
        logger.error("Email notification failed: %s", exc)


async def _send_slack(text: str, blocks: list | None = None) -> None:
    """POST a message to a Slack incoming webhook."""
    try:
        payload: dict = {"text": text}
        if blocks:
            payload["blocks"] = blocks

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(settings.slack_webhook_url, json=payload)
            if resp.status_code != 200:
                logger.error("Slack webhook returned %d: %s", resp.status_code, resp.text)
            else:
                logger.info("Slack notification sent")
    except Exception as exc:
        logger.error("Slack notification failed: %s", exc)


def _build_email_html(domain: str, scan_id: str, findings: list[dict]) -> str:
    rows = ""
    for f in findings[:10]:  # cap at 10 in email
        rows += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #e5e7eb;">
            <strong style="color:#991b1b;">{escape(f.get('title',''))}</strong><br>
            <a href="{escape(f.get('url',''))}" style="color:#1d4ed8;font-size:12px;">
              {escape(f.get('url',''))}
            </a>
          </td>
          <td style="padding:8px;border-bottom:1px solid #e5e7eb;text-align:center;
                     color:#991b1b;font-weight:bold;">
            {f.get('cvss_score') or '-'}
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"/></head>
<body style="font-family:Arial,sans-serif;color:#111;background:#fff;padding:24px;">
  <h2 style="color:#991b1b;margin:0 0 8px;">
    PantauInd - Critical Findings Detected
  </h2>
  <p style="color:#6b7280;font-size:13px;margin:0 0 20px;">
    Domain: <strong>{escape(domain)}</strong> &nbsp;|&nbsp;
    Scan ID: <code style="background:#f3f4f6;padding:2px 6px;border-radius:3px;">{escape(scan_id[:8])}</code>
  </p>
  <table style="width:100%;border-collapse:collapse;font-size:13px;">
    <thead>
      <tr style="background:#fef2f2;">
        <th style="text-align:left;padding:8px;border-bottom:2px solid #fca5a5;color:#991b1b;">
          Finding
        </th>
        <th style="padding:8px;border-bottom:2px solid #fca5a5;color:#991b1b;">CVSS</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="margin-top:20px;font-size:12px;color:#9ca3af;">
    PantauInd - Indonesian Government &amp; Academic Website Security Scanner
  </p>
</body>
</html>"""


def _build_slack_blocks(domain: str, scan_id: str, findings: list[dict]) -> list:
    lines = [f"*{escape(f.get('title',''))}*\n<{f.get('url','')}>" for f in findings[:5]]
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "PantauInd - Critical Findings"}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Domain:* `{domain}`\n*Scan ID:* `{scan_id[:8]}`\n"
                        f"*{len(findings)} critical finding(s) detected*",
            }
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n\n".join(lines) or "No details"},
        },
    ]


async def notify_critical_findings(
    domain: str,
    scan_id: str,
    findings: list[dict],
) -> None:
    """
    Send email and/or Slack notification for Critical findings.
    Both channels are non-fatal. Called from pipeline.py alongside notify_webhook().
    """
    if not findings:
        return

    if _email_configured():
        subject = f"[PantauInd] {len(findings)} Critical Finding(s) on {domain}"
        html = _build_email_html(domain, scan_id, findings)
        await _send_email(subject, html)

    if _slack_configured():
        text = f":rotating_light: PantauInd: {len(findings)} critical finding(s) on `{domain}`"
        blocks = _build_slack_blocks(domain, scan_id, findings)
        await _send_slack(text, blocks)

"""Transactional email for marketer notifications (Scout done, etc.)."""

from __future__ import annotations

import html as html_lib
import logging
import os
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class NotifyEmailRequest(BaseModel):
    to: str = Field(min_length=3, max_length=254)
    kind: str = Field(min_length=2, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=12000)
    href: str | None = Field(default=None, max_length=500)
    html: str | None = Field(default=None, max_length=40000)


def _sink_path() -> Path:
    raw = os.environ.get("NOTIFY_EMAIL_SINK", "/tmp/rivalradar-notify-emails.log")
    return Path(raw)


def recent_sunk_emails(*, limit: int = 20) -> list[dict[str, str]]:
    """Parse the local sink file (no-API-key path) into recent rows."""
    path = _sink_path()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, str]] = []
    for line in reversed(lines):
        if not line.strip():
            continue
        parts = line.split("|", 4)
        if len(parts) < 4:
            continue
        kind, to, subject, body = parts[0], parts[1], parts[2], parts[3]
        href = parts[4] if len(parts) > 4 else ""
        out.append(
            {
                "kind": kind,
                "to": to,
                "subject": subject,
                "body": body,
                "href": href,
                "channel": "sink",
            }
        )
        if len(out) >= limit:
            break
    return out


def _render_html(req: NotifyEmailRequest) -> str:
    if req.html and req.html.strip():
        inner = req.html.strip()
    else:
        escaped = html_lib.escape(req.body).replace("\n", "<br>\n")
        inner = f'<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;font-size:14px;line-height:1.5;color:#111;">{escaped}</div>'
    link = (
        f'<p style="margin-top:16px;"><a href="{html_lib.escape(req.href)}">Open in RivalRadar</a></p>'
        if req.href
        else ""
    )
    return inner + link


async def send_notify_email(req: NotifyEmailRequest) -> dict[str, str]:
    """Send via Resend when RESEND_API_KEY is set; otherwise append to a local sink file.

    Without an API key there is no outbound SMTP — the sink file is the delivery
    record for local/dev so the full notify path can be verified end-to-end.
    """
    subject = f"[RivalRadar] {req.title}"
    html = _render_html(req)
    api_key = (os.environ.get("RESEND_API_KEY") or "").strip()
    from_addr = (os.environ.get("NOTIFY_EMAIL_FROM") or "RivalRadar <onboarding@resend.dev>").strip()

    if api_key:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": from_addr,
                        "to": [str(req.to)],
                        "subject": subject,
                        "html": html,
                        "text": req.body,
                    },
                )
            if response.status_code >= 400:
                logger.warning("Resend email failed: %s %s", response.status_code, response.text[:300])
                return {"status": "error", "detail": response.text[:200], "channel": "resend"}
            logger.info("notify email sent via Resend to %s", req.to)
            return {"status": "sent", "channel": "resend", "to": str(req.to)}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Resend email error: %s", exc)
            return {"status": "error", "detail": str(exc)[:200], "channel": "resend"}

    # Dev / no-key sink — still proves the notify path end-to-end.
    line = f"{req.kind}|{req.to}|{subject}|{req.body.replace(chr(10), ' / ')}|{req.href or ''}\n"
    path = _sink_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError as exc:
        logger.warning("email sink write failed: %s", exc)
        return {"status": "error", "detail": str(exc)[:200], "channel": "sink"}
    logger.info("notify email sunk to %s for %s (no RESEND_API_KEY — not mailed)", path, req.to)
    return {
        "status": "sunk",
        "channel": "sink",
        "path": str(path),
        "to": str(req.to),
        "detail": (
            "No RESEND_API_KEY — email was written to the gateway sink file, "
            "not delivered to an inbox."
        ),
    }

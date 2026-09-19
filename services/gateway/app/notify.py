"""Transactional email for marketer notifications (Scout done, etc.)."""

from __future__ import annotations

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
    body: str = Field(min_length=1, max_length=2000)
    href: str | None = Field(default=None, max_length=500)


def _sink_path() -> Path:
    raw = os.environ.get("NOTIFY_EMAIL_SINK", "/tmp/rivalradar-notify-emails.log")
    return Path(raw)


async def send_notify_email(req: NotifyEmailRequest) -> dict[str, str]:
    """Send via Resend when RESEND_API_KEY is set; otherwise append to a local sink file."""
    subject = f"[RivalRadar] {req.title}"
    html = (
        f"<p>{req.body}</p>"
        + (f'<p><a href="{req.href}">Open in RivalRadar</a></p>' if req.href else "")
    )
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
                    },
                )
            if response.status_code >= 400:
                logger.warning("Resend email failed: %s %s", response.status_code, response.text[:300])
                return {"status": "error", "detail": response.text[:200], "channel": "resend"}
            return {"status": "sent", "channel": "resend"}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Resend email error: %s", exc)
            return {"status": "error", "detail": str(exc)[:200], "channel": "resend"}

    # Dev / no-key sink — still proves the notify path end-to-end.
    line = f"{req.kind}|{req.to}|{subject}|{req.body}|{req.href or ''}\n"
    path = _sink_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError as exc:
        logger.warning("email sink write failed: %s", exc)
        return {"status": "error", "detail": str(exc)[:200], "channel": "sink"}
    logger.info("notify email sunk to %s for %s", path, req.to)
    return {"status": "sunk", "channel": "sink", "path": str(path)}

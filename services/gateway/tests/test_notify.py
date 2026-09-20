from app.notify import NotifyEmailRequest, recent_sunk_emails, send_notify_email


async def test_notify_email_sinks_without_resend(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    sink = tmp_path / "emails.log"
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("NOTIFY_EMAIL_SINK", str(sink))
    result = await send_notify_email(
        NotifyEmailRequest(
            to="marketer@example.com",
            kind="scout_done",
            title="Scout finished — Pixis",
            body="12 posts in the window.",
            href="http://localhost:3000/mission",
        )
    )
    assert result["status"] == "sunk"
    assert result["channel"] == "sink"
    assert "No RESEND_API_KEY" in result["detail"]
    assert sink.exists()
    text = sink.read_text(encoding="utf-8")
    assert "scout_done" in text
    assert "marketer@example.com" in text
    assert "Scout finished" in text
    recent = recent_sunk_emails(limit=5)
    assert recent[0]["to"] == "marketer@example.com"
    assert recent[0]["kind"] == "scout_done"


async def test_notify_email_prefers_html(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    sink = tmp_path / "emails.log"
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("NOTIFY_EMAIL_SINK", str(sink))
    result = await send_notify_email(
        NotifyEmailRequest(
            to="marketer@example.com",
            kind="scout_done",
            title="Scout finished — Pixis",
            body="plain metrics",
            html="<p><strong>22 posts</strong> · brand 10</p>",
            href="http://localhost:3000/mission",
        )
    )
    assert result["status"] == "sunk"
    assert "plain metrics" in sink.read_text(encoding="utf-8")


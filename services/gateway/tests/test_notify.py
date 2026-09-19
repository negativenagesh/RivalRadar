from app.notify import NotifyEmailRequest, send_notify_email


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
    assert sink.exists()
    text = sink.read_text(encoding="utf-8")
    assert "scout_done" in text
    assert "marketer@example.com" in text
    assert "Scout finished" in text

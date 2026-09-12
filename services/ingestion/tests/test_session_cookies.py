from app.connectors.session_cookies import cookies_from_sessions, sanitize_playwright_cookies


def test_cookies_from_sessions_list_and_flat() -> None:
    cookies = cookies_from_sessions(
        {
            "linkedin": {
                "cookies": [
                    {"name": "li_at", "value": "abc", "domain": ".linkedin.com"},
                ]
            },
            "x": {"auth_token": "tok"},
        },
        platforms={"linkedin", "x"},
    )
    assert any(c["name"] == "li_at" and c["value"] == "abc" for c in cookies)
    assert any(c["name"] == "auth_token" and c["domain"] == ".x.com" for c in cookies)


def test_cookies_skips_other_platforms() -> None:
    cookies = cookies_from_sessions(
        {"linkedin": {"cookies": [{"name": "li_at", "value": "x"}]}},
        platforms={"instagram"},
    )
    assert cookies == []


def test_sanitize_drops_invalid_fields() -> None:
    cleaned = sanitize_playwright_cookies(
        [
            {
                "name": "sessionid",
                "value": "abc",
                "domain": ".instagram.com",
                "path": "/",
                "expires": -1,
                "sameSite": "no_restriction",
                "partitionKey": {"topLevelSite": "https://instagram.com"},
                "size": 12,
            },
            {"name": "bad", "value": "x"},  # no domain/url
            {
                "name": "auth",
                "value": "1",
                "url": "https://www.linkedin.com/",
                "sameSite": "Lax",
            },
        ]
    )
    assert len(cleaned) == 2
    ig = next(c for c in cleaned if c["name"] == "sessionid")
    assert "expires" not in ig
    assert ig["sameSite"] == "None"
    assert ig["secure"] is True
    assert "partitionKey" not in ig
    assert next(c for c in cleaned if c["name"] == "auth")["url"].startswith("https://")

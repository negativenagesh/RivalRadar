from app.connectors.session_cookies import cookies_from_sessions


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

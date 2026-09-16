"""Unit tests for quick connect pairing + cookie normalization."""

from __future__ import annotations

import pytest
from app.quick_connect import (
    consume_pairing_code,
    issue_pairing_code,
    normalize_cookies,
)


def test_pairing_code_round_trip() -> None:
    code, expires_in = issue_pairing_code("default")
    assert len(code) == 6
    assert expires_in == 300
    assert consume_pairing_code(code.lower(), "default") is True
    # One-time use
    assert consume_pairing_code(code, "default") is False


def test_pairing_rejects_wrong_workspace() -> None:
    code, _ = issue_pairing_code("ws-a")
    assert consume_pairing_code(code, "ws-b") is False
    assert consume_pairing_code(code, "ws-a") is True


def test_normalize_linkedin_requires_li_at() -> None:
    with pytest.raises(ValueError, match="li_at"):
        normalize_cookies("linkedin", [{"name": "JSESSIONID", "value": "ajax:1"}])


def test_normalize_linkedin_ok() -> None:
    cookies = normalize_cookies(
        "linkedin",
        [
            {"name": "li_at", "value": "AQFxxx", "domain": ".linkedin.com", "path": "/", "httpOnly": True},
            {"name": "JSESSIONID", "value": "ajax:123", "domain": ".linkedin.com"},
            {"name": "noise", "value": "x"},
        ],
    )
    names = {c["name"] for c in cookies}
    assert "li_at" in names
    assert "JSESSIONID" in names
    assert "noise" not in names


def test_normalize_x_requires_auth_token() -> None:
    with pytest.raises(ValueError, match="auth_token"):
        normalize_cookies("x", [{"name": "ct0", "value": "abc"}])


def test_normalize_instagram_sessionid() -> None:
    cookies = normalize_cookies(
        "instagram",
        [{"name": "sessionid", "value": "123%3Aabc", "expirationDate": 2_000_000_000}],
    )
    assert cookies[0]["name"] == "sessionid"
    assert cookies[0]["expires"] == 2_000_000_000
    assert cookies[0]["domain"] == ".instagram.com"

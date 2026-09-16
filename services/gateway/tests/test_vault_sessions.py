from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from app.vault_sessions import cookies_for_platform, load_vaulted_platform_sessions


def test_cookies_for_platform_from_cookies_and_storage_state() -> None:
    sessions: dict[str, dict[str, Any]] = {
        "linkedin": {
            "cookies": [{"name": "li_at", "value": "x", "domain": ".linkedin.com"}],
        },
        "x": {
            "storage_state": {
                "cookies": [{"name": "auth_token", "value": "y", "domain": ".x.com"}],
            }
        },
    }
    assert cookies_for_platform(sessions, "linkedin")[0]["name"] == "li_at"
    assert cookies_for_platform(sessions, "x")[0]["name"] == "auth_token"
    assert cookies_for_platform(sessions, "instagram") == []


@pytest.mark.asyncio
async def test_load_vaulted_platform_sessions_decrypts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = MagicMock()
    row.platform = "linkedin"
    row.encrypted_blob = "blob"

    class _Scalars:
        def all(self) -> list[Any]:
            return [row]

    class _Session:
        async def scalars(self, _q: object) -> _Scalars:
            return _Scalars()

    monkeypatch.setattr(
        "app.vault_sessions.decrypt_json",
        lambda _b: {"cookies": [{"name": "li_at", "value": "tok"}]},
    )
    out = await load_vaulted_platform_sessions(
        _Session(),  # type: ignore[arg-type]
        platforms={"linkedin"},
    )
    assert "linkedin" in out
    assert out["linkedin"]["cookies"][0]["name"] == "li_at"

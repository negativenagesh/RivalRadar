
from app.main import _viewer_url


def test_viewer_url_prefers_public_env(monkeypatch) -> None:
    monkeypatch.setenv(
        "PUBLIC_VIEWER_URL",
        "https://connect.example/vnc.html?autoconnect=1",
    )
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://ignored.example")
    assert _viewer_url() == "https://connect.example/vnc.html?autoconnect=1"


def test_viewer_url_from_render_external(monkeypatch) -> None:
    monkeypatch.delenv("PUBLIC_VIEWER_URL", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://rivalradar-connect.onrender.com/")
    assert _viewer_url() == (
        "https://rivalradar-connect.onrender.com/vnc.html?autoconnect=1&resize=scale"
    )


def test_viewer_url_none_without_env(monkeypatch) -> None:
    monkeypatch.delenv("PUBLIC_VIEWER_URL", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    assert _viewer_url() is None

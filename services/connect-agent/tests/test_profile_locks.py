from pathlib import Path

from app.browser import release_profile_locks


def test_release_profile_locks_removes_singleton_files(tmp_path: Path) -> None:
    profile = tmp_path / "linkedin"
    profile.mkdir()
    (profile / "SingletonLock").symlink_to("deadhost-585")
    (profile / "SingletonCookie").write_text("cookie", encoding="utf-8")
    (profile / "SingletonSocket").symlink_to("/tmp/missing-socket")
    # Real profile data must survive.
    (profile / "Default").mkdir()
    (profile / "Default" / "Cookies").write_text("keep-me", encoding="utf-8")

    removed = release_profile_locks(profile)

    assert set(removed) == {"SingletonLock", "SingletonCookie", "SingletonSocket"}
    assert not (profile / "SingletonLock").exists()
    assert not (profile / "SingletonCookie").exists()
    assert not (profile / "SingletonSocket").exists()
    assert (profile / "Default" / "Cookies").read_text(encoding="utf-8") == "keep-me"


def test_release_profile_locks_noop_when_clean(tmp_path: Path) -> None:
    profile = tmp_path / "instagram"
    profile.mkdir()
    assert release_profile_locks(profile) == []

from app.connectors.social_feed_parse import (
    _is_nav_destroy,
    external_id_for,
    normalize_platform,
    parse_count,
)


def test_parse_count_suffixes() -> None:
    assert parse_count("1,234") == 1234
    assert parse_count("12.5K") == 12500
    assert parse_count("2M") == 2_000_000
    assert parse_count("") == 0


def test_external_id_instagram() -> None:
    assert (
        external_id_for("instagram", "https://www.instagram.com/p/AbCdEf12345/")
        == "instagram:AbCdEf12345"
    )
    assert normalize_platform("twitter") == "x"


def test_external_id_linkedin_activity() -> None:
    eid = external_id_for(
        "linkedin",
        "https://www.linkedin.com/feed/update/urn:li:activity:1234567890/",
    )
    assert eid.startswith("linkedin:")
    assert "1234567890" in eid


def test_nav_destroy_detection() -> None:
    assert _is_nav_destroy(
        RuntimeError(
            "Page.eval_on_selector_all: Execution context was destroyed, "
            "most likely because of a navigation"
        )
    )
    assert not _is_nav_destroy(RuntimeError("timeout 30000ms exceeded"))

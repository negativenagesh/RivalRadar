from app.connectors.social_feed import _profile_entry_url
from app.connectors.social_feed_parse import (
    _is_nav_destroy,
    absolutize,
    canonicalize_post_url,
    external_id_for,
    normalize_platform,
    parse_count,
)
from app.connectors.social_profile.targets import ProfileTarget


def test_parse_count_suffixes() -> None:
    assert parse_count("1,234") == 1234
    assert parse_count("12.5K") == 12500
    assert parse_count("2M") == 2_000_000
    assert parse_count("") == 0
    assert parse_count(".") == 0
    assert parse_count("N/A") == 0
    assert parse_count("likes") == 0


def test_canonicalize_x_photo_and_analytics_urls() -> None:
    assert (
        canonicalize_post_url("x", "https://x.com/Pixis_AI/status/1896962592331219042/photo/1")
        == "https://x.com/Pixis_AI/status/1896962592331219042"
    )
    assert (
        canonicalize_post_url(
            "x", "https://x.com/Pixis_AI/status/1896962592331219042/analytics"
        )
        == "https://x.com/Pixis_AI/status/1896962592331219042"
    )
    assert (
        canonicalize_post_url(
            "instagram", "https://www.instagram.com/pixis_ai/p/DdGWu5tmj5o/?img_index=2"
        )
        == "https://www.instagram.com/p/DdGWu5tmj5o/"
    )


def test_absolutize_relative_hrefs() -> None:
    assert (
        absolutize("https://x.com/Pixis_AI", "/Pixis_AI/status/123")
        == "https://x.com/Pixis_AI/status/123"
    )


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


def test_linkedin_company_posts_entry_url() -> None:
    target = ProfileTarget(
        handle="@pixisai",
        platform="linkedin",
        url="https://www.linkedin.com/company/pixisai",
    )
    assert _profile_entry_url(target, "linkedin").endswith("/company/pixisai/posts")
    already = ProfileTarget(
        handle="@pixisai",
        platform="linkedin",
        url="https://www.linkedin.com/company/pixisai/posts",
    )
    assert _profile_entry_url(already, "linkedin").endswith("/posts")

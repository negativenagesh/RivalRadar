from app.connectors.social_feed_parse import external_id_for, normalize_platform, parse_count


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

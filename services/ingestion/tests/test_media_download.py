from app.connectors.media_download import _ext_from_content_type


def test_ext_from_content_type_images() -> None:
    assert _ext_from_content_type("image/png") == ".png"
    assert _ext_from_content_type("image/webp; charset=binary") == ".webp"
    assert _ext_from_content_type("image/gif") == ".gif"
    assert _ext_from_content_type("image/jpeg") == ".jpg"


def test_ext_from_content_type_playable_videos() -> None:
    assert _ext_from_content_type("video/mp4") == ".mp4"
    assert _ext_from_content_type("video/webm") == ".webm"
    assert _ext_from_content_type("video/quicktime") == ".mov"
    assert _ext_from_content_type("video/x-matroska") == ".mkv"
    # Unknown video/* must not collapse to .jpg (breaks Findings <video>).
    assert _ext_from_content_type("video/ogg") == ".mp4"

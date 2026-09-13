from app.agents.prompts import (
    COMMENT_SNIPER,
    FORMAT_DIRECTOR,
    FORMAT_SPECS,
    IMAGE_NEGATIVES,
    INTEL_CHIEF,
    MEME_LORD,
    PLAY_CALLER,
    VOICE_GUARD,
)


def test_intel_chief_does_not_invent_metrics() -> None:
    assert "NEVER invent metrics" in INTEL_CHIEF
    assert "JSON" in INTEL_CHIEF
    assert "markdown" in INTEL_CHIEF.lower()


def test_play_caller_writes_extra_markdown_reports() -> None:
    assert "reports" in PLAY_CALLER
    assert "markdown" in PLAY_CALLER


def test_format_agents_include_voice_guard_rules() -> None:
    blob = f"{FORMAT_DIRECTOR}\n{MEME_LORD}\n{VOICE_GUARD}\n{IMAGE_NEGATIVES}"
    assert "Forbidden claims" in FORMAT_DIRECTOR
    assert "no fake metrics" in FORMAT_DIRECTOR.lower()
    assert "no rival" in blob.lower()
    assert "Voice Guard" in VOICE_GUARD or "forbidden" in VOICE_GUARD.lower()


def test_comment_sniper_is_approve_only_human() -> None:
    assert "Approve" in COMMENT_SNIPER
    assert "Great post" in COMMENT_SNIPER
    assert "hashtag" in COMMENT_SNIPER.lower()


def test_format_specs_cover_studio_chips() -> None:
    expected = {
        "meme",
        "founder_2am",
        "receipt_carousel",
        "myth_bust",
        "hot_take",
        "product_story",
        "trend_jack",
        "comparison",
        "ugc",
        "case_study_15s",
        "poll",
        "linkedin_thought",
        "x_thread",
        "parody_play",
    }
    assert expected <= set(FORMAT_SPECS)

from app.agents.prompts import (
    COMMENT_SNIPER,
    FORMAT_DIRECTOR,
    FORMAT_SPECS,
    IMAGE_NEGATIVES,
    INTEL_CHIEF,
    MEME_LORD,
    PLATFORM_SCOUT,
    PLAY_CALLER,
    VOICE_GUARD,
)


def test_intel_chief_does_not_invent_metrics() -> None:
    assert "NEVER invent metrics" in INTEL_CHIEF
    assert "JSON" in INTEL_CHIEF
    assert "Platform evals" in INTEL_CHIEF
    assert "markdown" in INTEL_CHIEF.lower()


def test_play_caller_writes_extra_markdown_reports() -> None:
    assert "reports" in PLAY_CALLER
    assert "markdown" in PLAY_CALLER


def test_platform_scout_covers_every_platform() -> None:
    assert "Platform Scout" in PLATFORM_SCOUT
    assert "platforms" in PLATFORM_SCOUT
    assert "competitive" in PLATFORM_SCOUT
    assert "companies[].platforms" in PLATFORM_SCOUT


def test_format_agents_include_voice_guard_rules() -> None:
    blob = f"{FORMAT_DIRECTOR}\n{MEME_LORD}\n{VOICE_GUARD}\n{IMAGE_NEGATIVES}"
    assert "Forbidden claims" in FORMAT_DIRECTOR
    assert "no fake metrics" in FORMAT_DIRECTOR.lower()
    assert "no rival" in blob.lower()
    assert "Voice Guard" in VOICE_GUARD or "forbidden" in VOICE_GUARD.lower()
    assert "Gen Z" in MEME_LORD or "GenZ" in MEME_LORD
    assert "letter-perfect" in IMAGE_NEGATIVES.lower() or "perfect English spelling" in IMAGE_NEGATIVES
    assert "ZERO readable text" in MEME_LORD or "no other readable text" in FORMAT_SPECS["meme"].lower()
    assert "ROAST" in MEME_LORD.upper() or "roast" in MEME_LORD
    assert "NEVER invent metrics" in MEME_LORD or "never invent metrics" in MEME_LORD.lower()


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

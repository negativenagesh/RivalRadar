from typing import Any


def make_digest(*, digest_id: str = "digest-1", clusters: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": digest_id,
        "generated_at": "2026-08-30T00:00:00Z",
        "clusters": clusters
        if clusters is not None
        else [
            {
                "format": "founder_post",
                "dominant_theme": "sustainability",
                "post_count": 2,
                "total_engagement": 1000,
                "avg_engagement": 500.0,
                "top_post_id": "p1",
                "top_post_caption": "we planted trees",
                "account_ids": ["acc-1"],
            }
        ],
        "trending_themes": ["sustainability"],
        "gap_themes": ["sustainability"],
        "post_count": 5,
    }


def make_generation_response(*, caption: str = "an on-brand caption") -> dict[str, Any]:
    return {
        "caption": caption,
        "image_concept": "a warm photo concept",
        "image_mime_type": "image/png",
        "image_data_base64": "ZmFrZS1pbWFnZS1ieXRlcw==",
        "voice_examples_used": ["halo-001"],
    }


def make_compliance_response(*, passed: bool = True) -> dict[str, Any]:
    return {
        "passed": passed,
        "rule_violations": [] if passed else [{"rule": "test rule", "category": "banned_claim", "matched_text": "x"}],
        "llm_safe": passed,
        "llm_reason": "" if passed else "flagged for testing",
    }

from app.voice.retrieval import VoiceCorpus, VoiceExample
from llm_provider import Message


def build_caption_prompt(
    corpus: VoiceCorpus,
    examples: list[VoiceExample],
    *,
    cluster_format: str,
    cluster_theme: str,
    competitor_caption: str,
) -> list[Message]:
    """Build the exact chat messages sent to the LLM for caption drafting.

    Kept as a pure function returning plain Message objects (no call to the
    provider) so the few-shot construction is unit-testable and inspectable
    on its own -- you can print/assert on exactly which examples were
    selected and how they were injected, without mocking an HTTP client.
    """
    system = (
        f"You are the social media voice of {corpus.brand_name}. "
        f"Brand voice: {corpus.brand_description}\n\n"
        "You will be shown examples of this brand's own past captions, then "
        "asked to draft a new one. Match the tone, sentence rhythm, and "
        "level of humor of the examples exactly. Do not use generic "
        "marketing language. Output only the caption text, nothing else."
    )

    example_block = "\n".join(f'- "{ex.caption}"' for ex in examples)

    user = (
        f"Here are {len(examples)} of this brand's own past captions, "
        f"chosen because they share themes with the post below:\n"
        f"{example_block}\n\n"
        f"A competitor just posted a high-engagement {cluster_format.replace('_', ' ')} "
        f'about "{cluster_theme}". Their caption was: "{competitor_caption}"\n\n'
        "Draft one on-brand caption responding to this trend in this brand's own voice. "
        "Do not copy or reference the competitor directly."
    )

    return [Message(role="system", content=system), Message(role="user", content=user)]


def build_image_concept_brief(*, cluster_format: str, cluster_theme: str, caption: str) -> str:
    return (
        f"Format: {cluster_format.replace('_', ' ')}. Theme: {cluster_theme}. "
        f"Paired caption: {caption}"
    )

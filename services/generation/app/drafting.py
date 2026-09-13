import base64
import logging

from app.config import settings
from app.schemas import DraftRequest, DraftResponse
from app.voice.prompt import build_caption_prompt, build_image_concept_brief
from app.voice.retrieval import VoiceCorpus, select_examples
from llm_provider import LLMProvider

logger = logging.getLogger(__name__)


async def draft_response(
    request: DraftRequest,
    corpus: VoiceCorpus,
    provider: LLMProvider,
) -> DraftResponse:
    examples = select_examples(
        corpus,
        [request.cluster_theme],
        count=settings.few_shot_example_count,
    )

    messages = build_caption_prompt(
        corpus,
        examples,
        cluster_format=request.cluster_format,
        cluster_theme=request.cluster_theme,
        competitor_caption=request.competitor_caption,
    )
    caption = await provider.complete(messages, temperature=0.8, max_tokens=200)
    caption = caption.strip().strip('"')

    image_brief = build_image_concept_brief(
        cluster_format=request.cluster_format,
        cluster_theme=request.cluster_theme,
        caption=caption,
    )
    style_hints = [corpus.brand_name, "on-brand, not competitor-mimicking"]
    image_concept = await provider.generate_image_concept(image_brief, style_hints=style_hints)

    image_mime_type: str | None = None
    image_data_base64: str | None = None
    try:
        image = await provider.generate_image(image_brief, style_hints=style_hints, aspect_ratio="1:1")
        image_mime_type = image.mime_type
        image_data_base64 = base64.b64encode(image.data).decode("ascii")
    except Exception:
        logger.warning("generate_image failed; falling back to text-only concept", exc_info=True)

    return DraftResponse(
        caption=caption,
        image_concept=image_concept.strip(),
        voice_examples_used=[ex.id for ex in examples],
        image_mime_type=image_mime_type,
        image_data_base64=image_data_base64,
    )

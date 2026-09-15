from llm_provider import ImageResult, Message


class FakeLLMProvider:
    """Deterministic stand-in for LLMProvider so tests never hit a real API."""

    def __init__(
        self,
        completion: str = "a fake caption",
        image_concept: str = "a fake concept",
        image_bytes: bytes = b"fake-image-bytes",
        image_mime_type: str = "image/png",
        raise_on_generate_image: bool = False,
    ) -> None:
        self.completion = completion
        self.image_concept_text = image_concept
        self.image_bytes = image_bytes
        self.image_mime_type = image_mime_type
        self.raise_on_generate_image = raise_on_generate_image
        self.last_messages: list[Message] | None = None
        self.last_image_brief: str | None = None
        self.last_aspect_ratio: str | None = None
        self.complete_calls = 0
        self.stream_chunks: list[str] | None = None

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> str:
        self.complete_calls += 1
        self.last_messages = messages
        return self.completion

    async def complete_stream(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ):
        self.complete_calls += 1
        self.last_messages = messages
        chunks = self.stream_chunks
        if chunks is None:
            # Chunk into ~24-char pieces so stream consumers get multiple deltas.
            text = self.completion
            chunks = [text[i : i + 24] for i in range(0, len(text), 24)] or [""]
        for piece in chunks:
            yield piece

    async def generate_image_concept(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
    ) -> str:
        self.last_image_brief = brief
        return self.image_concept_text

    async def generate_image(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
        aspect_ratio: str | None = None,
    ) -> ImageResult:
        self.last_aspect_ratio = aspect_ratio
        if self.raise_on_generate_image:
            raise RuntimeError("simulated image generation failure")
        return ImageResult(mime_type=self.image_mime_type, data=self.image_bytes)

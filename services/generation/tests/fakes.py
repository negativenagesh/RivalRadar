from llm_provider import Message


class FakeLLMProvider:
    """Deterministic stand-in for LLMProvider so tests never hit a real API."""

    def __init__(self, completion: str = "a fake caption", image_concept: str = "a fake concept") -> None:
        self.completion = completion
        self.image_concept_text = image_concept
        self.last_messages: list[Message] | None = None
        self.last_image_brief: str | None = None

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        self.last_messages = messages
        return self.completion

    async def generate_image_concept(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
    ) -> str:
        self.last_image_brief = brief
        return self.image_concept_text

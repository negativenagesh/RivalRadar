from llm_provider import Message


class FakeLLMProvider:
    """Deterministic stand-in for LLMProvider so tests never hit a real API."""

    def __init__(self, completion: str = '{"safe": true, "reason": ""}') -> None:
        self.completion = completion
        self.last_messages: list[Message] | None = None

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> str:
        self.last_messages = messages
        return self.completion

    async def generate_image_concept(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
    ) -> str:
        raise NotImplementedError("compliance service does not generate image concepts")

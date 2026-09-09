# llm_provider

Shared library implementing RivalRadar's pluggable LLM provider abstraction. See [ARCHITECTURE.md](../../ARCHITECTURE.md#model-provider-abstraction) for the design rationale.

## Usage

```python
from llm_provider import get_llm_provider, Message

provider = get_llm_provider()
text = await provider.complete([Message(role="user", content="Hello")])
```

Selected via `LLM_PROVIDER` (default `gemini`). Currently ships one adapter, `GeminiOpenAICompatProvider` (`gemini.py`), which talks to Gemini's OpenAI-compatible endpoint using the standard `openai` SDK — see [ai.google.dev/gemini-api/docs/openai](https://ai.google.dev/gemini-api/docs/openai).

## Env vars

- `LLM_PROVIDER` (default `gemini`)
- `GEMINI_API_KEY` (required for the gemini provider)
- `GEMINI_BASE_URL` (default `https://generativelanguage.googleapis.com/v1beta/openai/`)
- `GEMINI_TEXT_MODEL` (default `gemini-3.6-flash`)

## Tests

```bash
uv run pytest
```

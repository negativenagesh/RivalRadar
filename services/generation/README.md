# Generation Service

Drafts on-brand response content: captions voice-matched against a small corpus of the brand's own past posts (few-shot), and image concepts (structured text descriptions, not rendered images).

## API

- `GET /health` — liveness check.

Draft-generation endpoints land in Phase 4; contract will also be at `/docs` when running.

## Run standalone

```bash
cd services/generation
uv sync
cp .env.example .env   # needs a real GEMINI_API_KEY
uv run uvicorn app.main:app --reload --port 8003
```

## Env vars

See [.env.example](.env.example). Requires `GEMINI_API_KEY`. Uses `libs/llm_provider` (installed as an editable path dependency) rather than calling any vendor SDK directly.

## Tests

```bash
uv run pytest
```

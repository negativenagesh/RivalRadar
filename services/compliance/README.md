# Compliance Service

Runs every generated draft through a brand-safety/compliance check (banned claims, off-brand tone/color flags) before it reaches a human reviewer.

## API

- `GET /health` — liveness check.

Compliance-check endpoints land in Phase 5; contract will also be at `/docs` when running.

## Run standalone

```bash
cd services/compliance
uv sync
cp .env.example .env   # needs a real GEMINI_API_KEY
uv run uvicorn app.main:app --reload --port 8004
```

## Env vars

See [.env.example](.env.example). Requires `GEMINI_API_KEY` for the LLM-classifier pass; rule-based checks run with no external calls.

## Tests

```bash
uv run pytest
```

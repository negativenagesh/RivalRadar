# Gateway Service (BFF)

The only backend service the frontend talks to. Owns the Postgres schema for drafts and review state, and orchestrates calls to `intelligence`, `generation`, and `compliance`.

## API

- `GET /health` — liveness check.

Digest, draft, and review-approval endpoints land in Phase 6; contract will also be at `/docs` when running.

## Run standalone

```bash
cd services/gateway
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8000
```

## Env vars

See [.env.example](.env.example). Requires `DATABASE_URL`, `REDIS_URL`, and the internal service URLs for `intelligence`/`generation`/`compliance`.

## Tests

```bash
uv run pytest
```

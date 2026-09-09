# Intelligence Service

Clusters ingested competitor posts by format and theme, scores them by engagement, and produces the weekly trend-and-gap digest.

## API

- `GET /health` — liveness check.

Clustering/digest endpoints land in Phase 3; contract will also be at `/docs` when running.

## Run standalone

```bash
cd services/intelligence
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8002
```

## Env vars

See [.env.example](.env.example). Requires `DATABASE_URL` and `INGESTION_SERVICE_URL`.

## Tests

```bash
uv run pytest
```

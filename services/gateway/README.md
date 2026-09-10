# Gateway Service (BFF)

The only backend service the frontend talks to. Owns the Postgres schema for drafts and review state, orchestrates calls to `intelligence`, `generation`, and `compliance`, and streams draft-generation progress live over WebSocket via `libs/agent_events`.

## How draft generation works

`POST /drafts/generate` doesn't run the pipeline inline — it creates a `PipelineRun` row, kicks off a background task, and returns `{"run_id": ..., "status": "pending"}` immediately (`202`). The background task (`app/runs.py` → `app/pipeline.py`) then, for each cluster in the latest digest:

1. Calls `generation` for a caption + image concept (+ a real generated image, best-effort).
2. Calls `compliance` to check the caption.
3. Persists a `Draft` — **regardless of the compliance verdict**, so a human reviewer sees the flag rather than the draft silently disappearing.
4. Publishes each step onto the shared `agent_events` bus, keyed by `run_id`.

Poll `GET /pipeline-runs/{run_id}` for status/results, or connect to `WS /pipeline-runs/{run_id}/live` to watch it happen step by step (same mechanism ingestion's browser agent uses for its own live view).

The run is currently all-or-nothing: a single cluster's downstream failure marks the whole run `error` with no partial drafts persisted. See `CHANGELOG.md` for why this is a known, deliberately-left limitation rather than a bug.

## API

- `GET /health` — liveness check.
- `GET /digest/latest`, `POST /digest/generate` — proxy to `intelligence`.
- `POST /drafts/generate` — starts a background pipeline run, returns `202` + `run_id`.
- `GET /pipeline-runs/{run_id}` — poll run status/result.
- `WS /pipeline-runs/{run_id}/live` — live step-by-step progress.
- `GET /drafts` — list all persisted drafts, newest first.
- `POST /drafts/{id}/approve` — marks `ready_to_publish`. Compliance failure does **not** block this — the reviewer sees `compliance_passed`/`compliance_llm_reason` and can consciously override it.
- `POST /drafts/{id}/edit` — sets `edited_caption`, state → `edited`.
- `POST /drafts/{id}/reject` — state → `rejected`.
- `POST /ingestion/runs`, `GET /ingestion/runs/{id}` — proxy to `ingestion`'s own run-tracking endpoints.

Full interactive contract (Swagger UI) is at `/docs` when the service is running.

## Run standalone

```bash
cd services/gateway
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8000
```

## Env vars

See [.env.example](.env.example). Requires `DATABASE_URL`, `REDIS_URL` (used by `agent_events`), and the internal service URLs for `ingestion`/`intelligence`/`generation`/`compliance`.

## Tests

```bash
uv run pytest
```

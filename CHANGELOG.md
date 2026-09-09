# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning follows [SemVer](https://semver.org/).

## [Unreleased]

### Added
- Compliance service: rule-based checks (`app/rules.py`, banned claims + off-brand tone via regex) plus an LLM-classifier pass (`app/classifier.py`) for nuance regex can't catch. Both must pass. `POST /compliance/check` returns violations and reasoning. 17 tests including a "fails closed on unparseable classifier response" case. Verified live against the real Gemini API across clean, rule-violating, and subtly-problematic (competitor-mimicking) captions.
- Generation service: voice-matched caption + image-concept drafting. Tag-overlap retrieval (`app/voice/retrieval.py`) picks the brand's own past captions most relevant to a digest cluster's theme; the few-shot prompt construction is a pure, independently-testable function (`app/voice/prompt.py`) so the mechanism is inspectable rather than a black box. `POST /drafts/generate` returns the caption, an image concept, and exactly which voice examples were used. Verified live against the real Gemini API.
- Intelligence service: rule/tag-based clustering (`app/clustering.py`) grouping posts by format + dominant theme, engagement scoring, trending/gap-theme detection, a `Digest` model, and REST endpoints (`POST /digests/generate`, `GET /digests/latest`, `GET /digests`). Verified end-to-end against the real ingestion service via `docker compose`.
- Ingestion service: `CompetitorAccount`/`CompetitorPost` SQLAlchemy async models, a `Connector` protocol with a fixture-backed implementation (10 sample posts across 4 formats: meme, product-launch carousel, founder post, UGC repost), an idempotent `run_ingestion` pipeline, and REST endpoints (`POST /ingest/run`, `GET /accounts`, `GET /posts`) with full test coverage.

### Fixed
- `LLMProvider.complete` gained a `reasoning_effort` parameter: Gemini's OpenAI-compat endpoint counts hidden "thinking" tokens against `max_tokens`, which was silently truncating the compliance classifier's JSON output on some inputs (discovered live-testing against the real API — `total_tokens` was ~15x `completion_tokens`). Passing `reasoning_effort="low"` for the classifier's call fixed it; `"none"` is rejected by the API as an invalid argument, confirmed by testing both directly.
- Default Gemini model updated from `gemini-2.5-flash` to `gemini-3.6-flash`: the former returned a live 404 from the API ("no longer available to new users"), discovered while verifying the generation service end-to-end against the real Gemini API.
- `generation`/`compliance` Dockerfiles: the builder stage's venv path didn't match the runtime copy destination (same class of bug as the earlier ingestion/intelligence/gateway fix, but with an extra wrinkle from the `libs/llm_provider` relative path dependency); both stages now consistently use `/build/services/<name>` so the editable install's relative path and the venv shebang both resolve correctly.
- Every service's Dockerfile: the builder stage's venv was created at a different path than the runtime stage copied it to, so the `uvicorn` shebang pointed at a nonexistent interpreter path and every container crash-looped (`exec ... no such file or directory`). Builder and runtime paths now match.
- Repo scaffold: five FastAPI microservices (`ingestion`, `intelligence`, `generation`, `compliance`, `gateway`), each with its own `uv`-managed `pyproject.toml`, Dockerfile, and placeholder `/health` endpoint.
- Shared `libs/llm_provider` package: a pluggable `LLMProvider` protocol with a `GeminiOpenAICompatProvider` implementation, selected via `LLM_PROVIDER` env var.
- Root `docker-compose.yml` wiring Postgres, Redis, all five services, and a frontend placeholder.
- Shared lint/type-check config (`ruff`, `mypy`) and `.pre-commit-config.yaml`.
- `README.md`, `ARCHITECTURE.md`, root `.env.example` and per-service `.env.example` files.

## [0.1.0] - Unreleased
Initial scaffold — nothing publicly runnable end-to-end yet. Will be tagged once the full pipeline (ingestion → digest → generation → compliance → review UI) works via `docker compose up`.

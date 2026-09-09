# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning follows [SemVer](https://semver.org/).

## [Unreleased]

### Added
- Ingestion service: `CompetitorAccount`/`CompetitorPost` SQLAlchemy async models, a `Connector` protocol with a fixture-backed implementation (10 sample posts across 4 formats: meme, product-launch carousel, founder post, UGC repost), an idempotent `run_ingestion` pipeline, and REST endpoints (`POST /ingest/run`, `GET /accounts`, `GET /posts`) with full test coverage.

### Fixed
- Every service's Dockerfile: the builder stage's venv was created at a different path than the runtime stage copied it to, so the `uvicorn` shebang pointed at a nonexistent interpreter path and every container crash-looped (`exec ... no such file or directory`). Builder and runtime paths now match.
- Repo scaffold: five FastAPI microservices (`ingestion`, `intelligence`, `generation`, `compliance`, `gateway`), each with its own `uv`-managed `pyproject.toml`, Dockerfile, and placeholder `/health` endpoint.
- Shared `libs/llm_provider` package: a pluggable `LLMProvider` protocol with a `GeminiOpenAICompatProvider` implementation, selected via `LLM_PROVIDER` env var.
- Root `docker-compose.yml` wiring Postgres, Redis, all five services, and a frontend placeholder.
- Shared lint/type-check config (`ruff`, `mypy`) and `.pre-commit-config.yaml`.
- `README.md`, `ARCHITECTURE.md`, root `.env.example` and per-service `.env.example` files.

## [0.1.0] - Unreleased
Initial scaffold — nothing publicly runnable end-to-end yet. Will be tagged once the full pipeline (ingestion → digest → generation → compliance → review UI) works via `docker compose up`.

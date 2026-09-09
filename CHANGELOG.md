# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning follows [SemVer](https://semver.org/).

## [Unreleased]

### Added
- Repo scaffold: five FastAPI microservices (`ingestion`, `intelligence`, `generation`, `compliance`, `gateway`), each with its own `uv`-managed `pyproject.toml`, Dockerfile, and placeholder `/health` endpoint.
- Shared `libs/llm_provider` package: a pluggable `LLMProvider` protocol with a `GeminiOpenAICompatProvider` implementation, selected via `LLM_PROVIDER` env var.
- Root `docker-compose.yml` wiring Postgres, Redis, all five services, and a frontend placeholder.
- Shared lint/type-check config (`ruff`, `mypy`) and `.pre-commit-config.yaml`.
- `README.md`, `ARCHITECTURE.md`, root `.env.example` and per-service `.env.example` files.

## [0.1.0] - Unreleased
Initial scaffold — nothing publicly runnable end-to-end yet. Will be tagged once the full pipeline (ingestion → digest → generation → compliance → review UI) works via `docker compose up`.

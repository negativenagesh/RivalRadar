# Contributing

## Dev setup

This project uses [uv](https://docs.astral.sh/uv/) exclusively for Python dependency management — no pip, poetry, pipenv, or conda anywhere in the repo.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # if you don't have uv yet

# per service (or libs/llm_provider)
cd services/<name>
uv sync                # installs deps + creates .venv
uv run uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Full stack:

```bash
cp .env.example .env   # fill in GEMINI_API_KEY
docker compose up --build
```

## Running tests

```bash
cd services/<name>
uv run pytest
uv run ruff check .
uv run mypy .
```

## Commit conventions

Conventional Commits style prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`. Keep commits scoped to one logical change; update `CHANGELOG.md` under `[Unreleased]` alongside any user-facing change.

## Adding a new LLM provider

Implement the `LLMProvider` protocol in `libs/llm_provider/src/llm_provider/` (see `gemini.py` for the reference implementation), then add a branch in `factory.py`'s `get_llm_provider()`. Call sites in `generation`/`compliance` never change.

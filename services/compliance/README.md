# Compliance Service

Runs every generated draft through a brand-safety/compliance check (banned claims, off-brand tone/color flags) before it reaches a human reviewer.

## How the check works

Two independent passes, both must pass for a draft to be considered compliant:

1. **Rule-based checks** (`app/rules.py`) — deterministic regex patterns for banned claims (unsubstantiated medical/superiority/guarantee language) and off-brand tone (shouty caps, excessive punctuation, high-pressure urgency language). Free, instant, zero LLM calls.
2. **LLM classifier pass** (`app/classifier.py`) — catches nuance regex can't: misleading framing, competitor-mimicking, divisive topics. Uses `reasoning_effort="low"` on the Gemini call — Gemini's "thinking" tokens count against `max_tokens` on the OpenAI-compat endpoint, so a low-latency classification task explicitly asks for minimal reasoning rather than risking a truncated (and therefore unparseable) response. If the classifier's response can't be parsed as the expected JSON for any reason, the check **fails closed** (`safe: false`) rather than silently passing an unreviewed draft.

## API

- `GET /health` — liveness check.
- `POST /compliance/check` — runs both passes on `{"text": "..."}`, returns `passed`, `rule_violations`, and the LLM classifier's `llm_safe`/`llm_reason`.

Full interactive contract (Swagger UI) is at `/docs` when the service is running.

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

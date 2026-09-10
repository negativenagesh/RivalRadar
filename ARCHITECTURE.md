# Architecture

## Service boundaries — why these five

| Service | Owns | Why it's separate |
|---|---|---|
| `ingestion` | Competitor accounts/posts (fixture-backed connector interface) | Distinct data-acquisition concern; a real integration later (scraping, paid API) changes this service's internals only. |
| `intelligence` | Clustering, scoring, digest generation | CPU/logic-bound batch-style work, different scaling shape from the request/response services around it. |
| `generation` | Caption + image-concept drafting via LLM | The only service that needs low-latency LLM access on the hot path of "produce a draft" — isolating it means rate limits/retries/timeouts for the LLM don't leak into unrelated services. |
| `compliance` | Brand-safety rule checks + LLM classifier pass | A policy boundary as much as a technical one — keeping it separate means the "what can ship" logic has one owner and one audit trail, independent of how content was generated. |
| `gateway` | Postgres schema for drafts/review state, orchestration, the only service the frontend talks to | Classic BFF: the frontend gets one stable contract even as internal services evolve; internal services stay unreachable from the public network. |

`libs/llm_provider` is a shared library (not a service) — a Python package installed via `uv` path dependency into `generation` and `compliance`, since both need model access but neither should own the adapter. `libs/agent_events` is a second shared library: a small Redis-Streams-backed event bus that lets any service publish step-by-step progress for a long-running run (ingestion's browser agent, the gateway's draft-generation pipeline) to a `run_id`-keyed stream, with backlog replay for late-connecting clients and a live WebSocket tail.

## Data flow

1. `ingestion` loads competitor posts — either the `FixtureConnector` (static JSON, used in tests/CI) or the `SocialProfileConnector` (a real headless-Chromium/Playwright scrape of a bundled, ToS-free mock social-feed site), both implementing the same `Connector` protocol. `POST /ingest/run` runs in the background and returns a `run_id` immediately; progress streams live over `/ingest/runs/{run_id}/live` via `agent_events`.
2. `gateway`'s `GET /digest/generate` triggers `intelligence`, which pulls posts from `ingestion` over HTTP, clusters them by format/theme, scores by engagement, and persists a `Digest`.
3. `gateway`'s `POST /drafts/generate` starts a `PipelineRun` in the background (returns `run_id` immediately, `202`) that, for each cluster in the latest digest: calls `generation` for a caption + image concept + (when available) real generated image bytes, then calls `compliance` to check the caption, then persists a `Draft` — publishing each step onto `agent_events` so a frontend can watch it live over `/pipeline-runs/{run_id}/live`.
4. `generation` builds a few-shot prompt from a small brand-voice corpus and calls the LLM provider for the caption, a text image *concept*, and (best-effort) a real generated image via `LLMProvider.generate_image`; if image generation fails for any reason (unavailable model, quota, transient error) it logs a warning and falls back to the text-only concept rather than failing the whole draft.
5. `compliance` runs rule-based checks (banned claims, tone flags) and an LLM-classifier pass, returning pass/fail + reasons — independent of how the caption was generated.
6. `gateway` persists every draft regardless of compliance outcome, with review state (`pending`, `edited`, `rejected`, `ready_to_publish`) so a human reviewer sees the compliance verdict and can consciously override it. Only human approval (`POST /drafts/{id}/approve`) marks a draft `ready_to_publish`; actual publishing is a stubbed adapter — no real OAuth posting flow in this version.

Redis is used two ways: `agent_events` uses Redis Streams for live-progress pub/sub (a genuinely append-only, replayable use case Streams fit well), and `gateway` background pipeline runs are plain `asyncio.create_task` rather than a durable task queue — acceptable at this scale, but a background run is lost if the process restarts mid-run. A durable queue (Celery/RQ/Redis Streams-as-queue) is the documented upgrade path at higher volume — see trade-offs below.

## Model-provider abstraction

`libs/llm_provider` defines an `LLMProvider` protocol (`complete`, `generate_image_concept`, `generate_image`) with zero vendor imports in its interface. Call sites (`generation`, `compliance`) depend only on `get_llm_provider()`, a factory reading `LLM_PROVIDER` from the environment. Today `LLM_PROVIDER=gemini` resolves to `GeminiOpenAICompatProvider`, which uses the stock `openai` SDK pointed at Gemini's OpenAI-compatible endpoint (`GEMINI_BASE_URL`) rather than the `google-genai` SDK — this keeps the dependency surface to one well-known HTTP client shape and makes adding a second OpenAI-compatible provider (or true OpenAI) a matter of reusing the same adapter with different env vars, while a genuinely different API shape (e.g. Anthropic's Messages API) would get its own adapter module and a new branch in the factory.

**Model choice**: `gemini-3.6-flash` is the default text model — strong instruction-following at low latency/cost, appropriate for a portfolio-scale pipeline calling an LLM multiple times per digest (clustering summaries, captions, compliance classification). `complete` accepts an optional `reasoning_effort` hint because Gemini's hidden "thinking" tokens count against `max_tokens` on the OpenAI-compat endpoint — a low-latency classification task passes `"low"` rather than risking a truncated, unparseable response (found and fixed by live-testing against the real API; see `CHANGELOG.md`).

**Image generation**: `generate_image` calls `gemini-2.5-flash-image` via the same OpenAI-compat endpoint with `modalities: ["image", "text"]`. **On this project's free-tier API key, every image-generation model tried (`gemini-2.5-flash-image`, `gemini-3.1-flash-image-preview`, `gemini-3-pro-image-preview`) returns a live 429 with `limit: 0` on every quota metric** — confirmed by direct API calls, not just documentation. This is a hard "paid tier only" wall, not a temporary rate limit. The code path is real and correct (tested via a fake provider in `libs/llm_provider/tests/test_gemini_image.py`, and via `generation`'s graceful-degradation test), but has not been exercised against real returned image bytes on this account. `generate_image_concept` (a text-only description) is what actually gets exercised live end-to-end, and is what `generation` falls back to whenever `generate_image` raises — see `PORTFOLIO_NOTES.md` for the full story.

## Clustering approach (v1)

Rule/tag-based grouping (format + theme tags on each post, grouped and scored by engagement), not embeddings + vector similarity. See `services/intelligence/README.md` for the full justification — short version: explainable, zero extra infra (no vector DB), and accurate enough at fixture-data scale; embeddings are the documented upgrade path once real, higher-volume ingestion exists.

## Known trade-offs / what changes at real scale

- **Synchronous HTTP orchestration → message queue.** Direct async HTTP calls between `gateway` and downstream services are simple but couple their availability; at scale, `intelligence` → `generation` → `compliance` would move behind a durable queue (e.g. Redis Streams, SQS) so a downstream outage doesn't block ingestion, and so long LLM calls don't hold an HTTP connection open.
- **Rule/tag clustering → embeddings.** Fine at fixture/demo volume; would need real embedding-based clustering (and a vector index) once competitor volume and post variety grow past what hand-tagged rules can generalize over.
- **Local-disk object storage → S3-compatible store.** The object-store interface is written to be swappable, but v1 actually writes to a local volume; production would point the same interface at S3/R2/GCS.
- **No real publishing integration.** Approved drafts are marked `ready_to_publish` but nothing posts them; real OAuth + platform API integration (Meta, X, etc.) is deliberately out of scope for this version.
- **Single Postgres, no read replicas / multi-tenant isolation.** Fine for one brand's data; a real multi-tenant SaaS version would need per-tenant isolation and probably a different schema strategy.

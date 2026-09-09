# Architecture

## Service boundaries — why these five

| Service | Owns | Why it's separate |
|---|---|---|
| `ingestion` | Competitor accounts/posts (fixture-backed connector interface) | Distinct data-acquisition concern; a real integration later (scraping, paid API) changes this service's internals only. |
| `intelligence` | Clustering, scoring, digest generation | CPU/logic-bound batch-style work, different scaling shape from the request/response services around it. |
| `generation` | Caption + image-concept drafting via LLM | The only service that needs low-latency LLM access on the hot path of "produce a draft" — isolating it means rate limits/retries/timeouts for the LLM don't leak into unrelated services. |
| `compliance` | Brand-safety rule checks + LLM classifier pass | A policy boundary as much as a technical one — keeping it separate means the "what can ship" logic has one owner and one audit trail, independent of how content was generated. |
| `gateway` | Postgres schema for drafts/review state, orchestration, the only service the frontend talks to | Classic BFF: the frontend gets one stable contract even as internal services evolve; internal services stay unreachable from the public network. |

`libs/llm_provider` is a shared library (not a service) — a Python package installed via `uv` path dependency into `generation` and `compliance`, since both need model access but neither should own the adapter.

## Data flow

1. `ingestion` loads competitor posts from fixture data (v1) behind a `Connector` interface that a real scraper/API integration will implement later without touching callers.
2. `gateway` (or a scheduled job hitting `intelligence` directly) triggers `intelligence`, which pulls posts from `ingestion` over HTTP, clusters them by format/theme, scores by engagement, and persists a `Digest`.
3. `gateway` reads the digest and calls `generation` per digest cluster, which builds a few-shot prompt from a small brand-voice corpus and calls the LLM provider for a caption + image concept.
4. `generation`'s output is passed to `compliance`, which runs rule-based checks (banned claims, tone/color flags) and an LLM-classifier pass, returning pass/fail + reasons.
5. `gateway` persists everything as a `Draft` with review state (`pending`, `approved`, `edited`, `rejected`) and serves it to the frontend's review queue.
6. A human approves/edits/rejects in the Next.js UI; only `approved` drafts are marked `ready_to_publish`. Actual publishing is a stubbed adapter — no real OAuth posting flow in this version.

Redis is used by `gateway` for lightweight caching/task state (e.g. in-flight generation job status), not as a heavy message broker — the pipeline is orchestrated via direct async HTTP calls for v1, which is simpler to reason about and sufficient at this scale. A durable queue (e.g. Celery/RQ over Redis, or a proper broker) is the documented upgrade path at higher volume — see trade-offs below.

## Model-provider abstraction

`libs/llm_provider` defines an `LLMProvider` protocol (`complete`, `generate_image_concept`) with zero vendor imports in its interface. Call sites (`generation`, `compliance`) depend only on `get_llm_provider()`, a factory reading `LLM_PROVIDER` from the environment. Today `LLM_PROVIDER=gemini` resolves to `GeminiOpenAICompatProvider`, which uses the stock `openai` SDK pointed at Gemini's OpenAI-compatible endpoint (`GEMINI_BASE_URL`) rather than the `google-genai` SDK — this keeps the dependency surface to one well-known HTTP client shape and makes adding a second OpenAI-compatible provider (or true OpenAI) a matter of reusing the same adapter with different env vars, while a genuinely different API shape (e.g. Anthropic's Messages API) would get its own adapter module and a new branch in the factory.

**Model choice**: `gemini-3.6-flash` is the default text model — strong instruction-following at low latency/cost, appropriate for a portfolio-scale pipeline calling an LLM multiple times per digest (clustering summaries, captions, compliance classification). `generate_image_concept` returns a structured *text* description of an image (not pixels) in v1; the method signature is intentionally image-model-shaped so wiring in a real Gemini image-generation model later is additive, not a redesign.

## Clustering approach (v1)

Rule/tag-based grouping (format + theme tags on each post, grouped and scored by engagement), not embeddings + vector similarity. See `services/intelligence/README.md` for the full justification — short version: explainable, zero extra infra (no vector DB), and accurate enough at fixture-data scale; embeddings are the documented upgrade path once real, higher-volume ingestion exists.

## Known trade-offs / what changes at real scale

- **Synchronous HTTP orchestration → message queue.** Direct async HTTP calls between `gateway` and downstream services are simple but couple their availability; at scale, `intelligence` → `generation` → `compliance` would move behind a durable queue (e.g. Redis Streams, SQS) so a downstream outage doesn't block ingestion, and so long LLM calls don't hold an HTTP connection open.
- **Rule/tag clustering → embeddings.** Fine at fixture/demo volume; would need real embedding-based clustering (and a vector index) once competitor volume and post variety grow past what hand-tagged rules can generalize over.
- **Local-disk object storage → S3-compatible store.** The object-store interface is written to be swappable, but v1 actually writes to a local volume; production would point the same interface at S3/R2/GCS.
- **No real publishing integration.** Approved drafts are marked `ready_to_publish` but nothing posts them; real OAuth + platform API integration (Meta, X, etc.) is deliberately out of scope for this version.
- **Single Postgres, no read replicas / multi-tenant isolation.** Fine for one brand's data; a real multi-tenant SaaS version would need per-tenant isolation and probably a different schema strategy.

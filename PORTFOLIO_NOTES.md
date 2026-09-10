# Portfolio Notes

What I actually learned building RivalRadar — the kind of specifics I’d bring to an interview, not a generic “microservices are hard” list.

## What was genuinely hard

**Docker venv path bugs.** Every FastAPI service’s multi-stage Dockerfile created the uv venv at one path in the builder and copied it somewhere else at runtime. The `uvicorn` shebang still pointed at the builder path, so every container crash-looped with `exec … no such file or directory`. Generation and compliance had an extra wrinkle: the editable `libs/llm_provider` path dependency also had to resolve after the copy. Fix was boring and absolute — keep `/build/services/<name>` identical across stages so shebang and relative install paths both survive.

**Gemini “thinking” tokens vs `max_tokens`.** Live compliance runs returned truncated, unparseable JSON. Usage showed `total_tokens` ~15× `completion_tokens` — Gemini’s OpenAI-compat endpoint counts hidden thinking against the same budget. Adding `reasoning_effort="low"` fixed the classifier; `"none"` is rejected by the API. That’s the kind of bug you only find against a real key, not a fake provider.

**Free-tier image gen is `limit: 0`.** Every image model I tried (`gemini-2.5-flash-image`, `gemini-3.1-flash-image-preview`, `gemini-3-pro-image-preview`) returns a live 429 with `limit: 0` on every quota metric. Not a soft rate limit — a paid-tier wall. The code path is real (unit-tested with a fake provider; generation falls back to a text concept), but I’ve never seen real image bytes land on this account. I document that honestly rather than screenshotting a mock as if it worked.

**Next.js `LayoutProps` / typegen in CI.** App Router typed routes put `LayoutProps` / `PageProps` under `.next/types`. Bare `tsc --noEmit` in CI fails until you run `next typegen` first. Easy once you know it; opaque when CI is the first place you typecheck outside `next build`.

**`.gitignore` ate `frontend/src/lib`.** Root Python template ignored bare `lib/` / `lib64/`. That silently matched Next’s `src/lib/` (API client, types, utils), so `git add` dropped real source while the app looked fine locally. Caught when reviewing what was actually staged; removed the redundant entries (`.venv` already covers local envs).

**`create_all` is not a migration.** Gateway uses SQLAlchemy `create_all`. Adding `image_mime_type` / `image_data_base64` to an existing Postgres volume produced `UndefinedColumnError` — create_all won’t ALTER. Workaround today: `docker compose down -v`. Alembic is the obvious next step.

**All-or-nothing `PipelineRun`.** One cluster’s downstream 429 marks the whole run `error` and persists zero drafts, even if earlier clusters would have succeeded. Loud failure is better than silent partial data for a demo; wrong for real traffic.

**Browser agent + voice prompts.** The Playwright connector against a bundled mock social site forced real async browser lifecycle, screenshot/event streaming, and a ToS-safe demo target — not a mocked HTTP fetch. Voice matching was the other design problem: tag-overlap retrieval plus a pure, unit-testable `build_caption_prompt` so “which examples and how they were injected” is inspectable, not a black-box string dump.

## What I’d improve with more time

Per-cluster try/except so a `PipelineRun` can finish with partial drafts; Alembic from day one; a durable queue instead of `asyncio.create_task` for pipeline/ingestion runs; embedding-based clustering once volume leaves hand tags behind; paid-tier (or alternate) image gen so the happy path isn’t always the fallback; tighten generation’s caption post-processing for truncated LLM output.

## What breaks at scale

Synchronous HTTP orchestration couples availability — one slow LLM call holds the chain. In-process background tasks die on restart. Rule/tag clustering won’t generalize past fixture variety. Local object storage and a single Postgres with no tenant isolation are fine for one brand, not a SaaS. Free-tier Gemini quotas turn “generate drafts for every cluster” into a rate-limit lottery. No real publish path yet — `ready_to_publish` stops at the human gate by design.

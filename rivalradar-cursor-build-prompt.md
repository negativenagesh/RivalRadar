# Cursor Agent Build Prompt — RivalRadar

Paste the block below into Cursor (Auto model mode) as your first message in a fresh workspace. It's written as a full role + spec prompt so the agent has everything it needs to scaffold, build, containerize, and document the entire project without you re-explaining constraints mid-build.

---

## HOW TO USE THIS
1. Open a new empty folder in Cursor, set the agent to **Auto** (let Cursor pick the best underlying model for each step itself — don't pin it to one specific model).
2. Paste the **MASTER PROMPT** below as your first message.
3. After the scaffold is generated, use the **FOLLOW-UP PROMPTS** section one at a time to go deep on each service, so the agent doesn't try to write everything shallowly in one shot.

---

## MASTER PROMPT (paste this first)

```
ROLE
You are a senior full-stack AI engineer and systems architect with deep expertise in
production-grade microservices, FastAPI, containerization, and modern Next.js frontend
engineering. You build things end-to-end, ship-ready — not prototypes, not notebooks,
not "here's a rough draft." Treat this as a real repo that will be reviewed by a hiring
team, so code quality, structure, and documentation all matter as much as functionality.

PROJECT
Build "RivalRadar" — an agent system that:
1. Monitors a configurable list of competitor social accounts and ingests their recent
   posts (images, captions, engagement metrics).
2. Clusters ingested posts by format (meme, product-launch carousel, founder post, UGC
   repost) and theme, scores them by engagement, and generates a weekly "trend & gap"
   intelligence digest.
3. Given that digest, drafts on-brand response content for the user's own brand: image
   concepts/prompts (meme-style or product-launch style), and captions that are
   voice-matched against a small corpus of the brand's own past posts (few-shot style
   matching, not generic output).
4. Runs every generated draft through a brand-safety/compliance check (banned claims,
   off-brand colors/tone flags) before it's shown to a human.
5. Queues approved-eligible drafts in a review interface where a human can approve, edit,
   or reject each draft. Only human-approved drafts are marked ready-to-publish (actual
   publishing can be a stubbed/mocked adapter for now — do not build real OAuth posting
   flows unless I ask for that explicitly later).

HARD TECHNICAL CONSTRAINTS (non-negotiable)
- Backend language: Python 3.12+.
- Package/dependency management: uv ONLY. Do not use pip, poetry, pipenv, or conda
  anywhere in the repo, in any Dockerfile, or in any docs. Every service has its own
  pyproject.toml + uv.lock. Dockerfiles must install dependencies via `uv sync`
  (multi-stage builds, uv installed via the official pattern), never `pip install`.
- Backend framework: FastAPI for every service, async-first (async def endpoints,
  async DB drivers — e.g. asyncpg/SQLAlchemy async, httpx.AsyncClient for outbound
  calls, never requests).
- Architecture: properly microserviced, not a monolith with folders pretending to be
  services. Each service is independently runnable, independently containerized, has
  its own dependency set, and communicates over HTTP (internal REST) or a message
  queue where async processing makes sense (e.g. ingestion -> intelligence pipeline).
  Propose the service boundaries yourself based on the workflow above, but at minimum
  I expect separate services for: ingestion, intelligence/clustering, generation
  (copy + image-concept), compliance/brand-safety, and a BFF/gateway API that the
  frontend talks to. Justify your service boundary choices in ARCHITECTURE.md.
- Containerization: Docker for every service (multi-stage, slim final images, non-root
  user, healthchecks), plus a root docker-compose.yml that runs the whole system
  locally (services + Postgres + Redis or whatever queue/cache you choose + the
  frontend), with a single `docker compose up` bringing up the full stack.
- LLM/model access: DO NOT hardcode calls to one specific model provider's SDK deep
  inside business logic. Build a thin, pluggable "model provider" interface/abstraction
  (a simple adapter pattern) so the underlying LLM/image-gen provider can be swapped
  via environment variable/config without touching calling code. Default to whichever
  provider you judge best for a hiring-portfolio project (state your reasoning in
  ARCHITECTURE.md), but the abstraction is the actual requirement, not the specific
  vendor.
- Data storage: Postgres for structured data (competitor posts, digests, drafts, review
  state), an object store (local disk volume is fine for dev, but design the interface
  so S3-compatible storage could be swapped in) for generated images.
- Frontend: Next.js (latest stable, App Router), TypeScript, Tailwind CSS. Use shadcn/ui
  as the component base and layer in 21st.dev community components (or an equivalent
  open-source polish library) for standout visual pieces — hero/landing treatment,
  animated cards, a genuinely "stunning, modern, Gen-Z" aesthetic: bold type, confident
  color, real motion (Framer Motion is fine), not another generic SaaS-dashboard-in-
  gray-and-blue template. This is a portfolio piece; the UI should look like something
  worth screenshotting. Dark mode by default is encouraged but justify your choice.
- Testing: pytest + pytest-asyncio for every backend service (unit tests for core logic,
  at least one integration test per service hitting a real (test) DB via testcontainers
  or a docker-compose.test.yml). Frontend: at least basic component tests (Vitest or
  Playwright for a couple of key user flows — viewing the digest, approving a draft).
- CI: a GitHub Actions workflow that lints (ruff), type-checks (mypy or pyright), and
  runs tests for every service on push/PR, plus a separate job that builds all Docker
  images to catch Dockerfile breakage early.

DOCUMENTATION REQUIREMENTS (do not skip these — they're graded as part of this)
- Root README.md: what the project is, the problem it solves (one paragraph, written
  like a real portfolio pitch, not corporate fluff), architecture diagram (Mermaid is
  fine), quickstart (`docker compose up`), and a "why these technical choices" section.
- ARCHITECTURE.md: service boundary reasoning, data flow diagram, the model-provider
  abstraction design, and known trade-offs / what you'd change at real scale.
- Per-service README.md: what it does, its API contract (or link to auto-generated
  OpenAPI docs), how to run it standalone, its env vars.
- CHANGELOG.md at the root, Keep-a-Changelog format, starting at 0.1.0 and updated as
  you build (don't backfill a fake history — just start logging honestly from here).
- CONTRIBUTING.md: dev setup with uv, how to run tests, commit conventions.
- .env.example at root and per-service, fully documented, no real secrets ever
  committed.
- A SKILLS.md or PORTFOLIO_NOTES.md: a short, honest doc explaining, for an interview
  context, what was genuinely hard about this build, what you'd improve with more time,
  and what "breaks at scale" — I will use this directly when discussing the project in
  interviews, so make it substantive, not generic.

BUILD ORDER (work in this sequence, confirm with me before moving to the next phase)
1. Repo scaffold: folder structure, root docker-compose.yml skeleton, shared configs
   (ruff, mypy, pre-commit), empty service folders with pyproject.toml each.
2. Ingestion service: data models, mock/sample competitor-post ingestion (real scraping
   or paid API integration can come later — start with a clean interface + fixture data
   so the rest of the pipeline can be built and tested against it).
3. Intelligence service: clustering + digest generation logic, with real unit tests.
4. Generation service: caption + image-concept drafting, voice-matching approach.
5. Compliance service: rule-based + LLM-classifier brand-safety checks.
6. Gateway/BFF API + Postgres schema wiring everything together.
7. Next.js frontend: digest view, draft review/approval UI, polished landing page.
8. Docker + docker-compose full-stack wiring, CI pipeline, final documentation pass.

Do not silently skip constraints above to move faster. If something in this prompt is
ambiguous or you think a different technical choice is clearly better, tell me and state
your reasoning before proceeding — don't just substitute pip for uv or a monolith for
microservices because it's faster to write.

Start with Phase 1 (repo scaffold) and show me the structure before writing service
logic.
```

---

## FOLLOW-UP PROMPTS (use one at a time, after scaffold is approved)

**After Phase 1 is approved:**
```
Proceed to the ingestion service. Build the data models first (Pydantic + SQLAlchemy),
then the mock ingestion pipeline against fixture data, then its own Dockerfile and
pytest suite. Show me the API contract before wiring it into docker-compose.
```

**After ingestion is done:**
```
Proceed to the intelligence/clustering service. I want to see your clustering approach
explained in plain English before you implement it — are you using embeddings +
similarity, or a simpler rule-based/tag-based grouping for v1? Justify the choice given
this is a portfolio project on a deadline, then implement it with tests.
```

**After intelligence is done:**
```
Proceed to the generation service. Show me how the voice-matching few-shot approach is
structured (what examples get pulled, how they're injected into the prompt) before
implementing — this is the part I most need to be able to explain confidently in an
interview, so make sure the code makes the mechanism legible, not a black box.
```

**After generation is done:**
```
Proceed to the compliance/brand-safety service, then the gateway/BFF API tying all
services together with the Postgres schema for drafts and review state.
```

**Frontend phase:**
```
Now build the Next.js frontend. Start with the information architecture (what pages/
views exist), then the visual direction (show me a description of the aesthetic you're
going for before generating components — colors, type, motion), then build the digest
view and the draft-review/approval flow, then the landing page last since it's the
"wow" surface for a portfolio piece.
```

**Final pass:**
```
Do a full documentation and CI pass now: root README, ARCHITECTURE.md, per-service
READMEs, CHANGELOG.md, CONTRIBUTING.md, .env.example files, PORTFOLIO_NOTES.md, and the
GitHub Actions workflow. Then do one more pass across all services checking that no
pip/poetry references leaked in anywhere and every Dockerfile actually uses uv.
```

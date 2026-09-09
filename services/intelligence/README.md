# Intelligence Service

Clusters ingested competitor posts by format and theme, scores them by engagement, and produces the weekly trend-and-gap digest.

## Clustering approach

Rule/tag-based grouping, not embeddings + vector similarity. Each post from `ingestion` already carries a structured `format` (meme/product-launch-carousel/founder-post/UGC-repost) and a list of `theme_tags`; `cluster_posts` (`app/clustering.py`) groups posts by `(format, dominant_theme)` — the first tag on each post — sums/averages `engagement_score` per group, and ranks clusters by total engagement.

Trending themes are simply the most frequent tags across all ingested posts. "Gap" themes are tags used by 2+ competitor accounts (i.e. a real cross-competitor pattern, not one account's quirk) that aren't in the caller-supplied `brand_themes` set — a proxy for "competitors are doing this and you aren't."

This is deliberately simple for v1: no vector DB, no similarity threshold to tune, and every grouping decision is traceable to an exact tag match — you can explain any cluster by pointing at the `format`/`theme_tags` fields on its posts. The trade-off is real: tag-based clustering can't merge two competitors' differently-worded-but-semantically-same themes (e.g. "eco-friendly" vs "sustainability" would land in separate clusters). At meaningfully higher ingestion volume and tag vocabulary drift, embeddings-based clustering (e.g. sentence-transformer embeddings of caption + tags, clustered with HDBSCAN) is the documented upgrade path — see [ARCHITECTURE.md](../../ARCHITECTURE.md).

## API

- `GET /health` — liveness check.
- `POST /digests/generate` — fetches all posts from `ingestion` over HTTP, clusters them, persists and returns a `Digest`.
- `GET /digests/latest` — the most recently generated digest (404 if none exist yet).
- `GET /digests` — all digests, newest first.

Full interactive contract (Swagger UI) is at `/docs` when the service is running.

## Run standalone

```bash
cd services/intelligence
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8002
```

## Env vars

See [.env.example](.env.example). Requires `DATABASE_URL` and `INGESTION_SERVICE_URL`.

## Tests

```bash
uv run pytest
```

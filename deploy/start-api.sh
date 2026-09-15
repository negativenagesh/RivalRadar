#!/usr/bin/env bash
# Single Render web dyno: generation (Mission LLM) + gateway (public PORT).
# Defaults: gpt-oss text (NVIDIA) + Agnes image via env keys on the service.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-8000}"
GEN_PORT="${GENERATION_INTERNAL_PORT:-8003}"

export GENERATION_SERVICE_URL="${GENERATION_SERVICE_URL:-http://127.0.0.1:${GEN_PORT}}"
export MISSION_TEXT_MODEL="${MISSION_TEXT_MODEL:-gptoss}"
export MISSION_IMAGE_MODEL="${MISSION_IMAGE_MODEL:-agnes}"

# Never inject platform social cookies from env — users log in via Connect browser.
unset LINKEDIN_COOKIES TWITTER_COOKIES X_COOKIES INSTAGRAM_COOKIES YOUTUBE_COOKIES || true

cd "$ROOT/services/generation"
uvicorn app.main:app --host 127.0.0.1 --port "$GEN_PORT" &
GEN_PID=$!

cleanup() {
  kill "$GEN_PID" 2>/dev/null || true
}
trap cleanup EXIT

# Wait briefly so /ready can succeed after cold start.
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${GEN_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

cd "$ROOT/services/gateway"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"

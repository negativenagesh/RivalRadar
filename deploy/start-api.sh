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
export REDIS_URL="${REDIS_URL:-memory}"

# Never inject platform social cookies from env — users log in via Connect browser.
unset LINKEDIN_COOKIES TWITTER_COOKIES X_COOKIES INSTAGRAM_COOKIES YOUTUBE_COOKIES || true

GEN_UVICORN="$ROOT/services/generation/.venv/bin/uvicorn"
GW_UVICORN="$ROOT/services/gateway/.venv/bin/uvicorn"
if [[ ! -x "$GEN_UVICORN" ]]; then
  echo "missing generation uvicorn at $GEN_UVICORN" >&2
  exit 1
fi
if [[ ! -x "$GW_UVICORN" ]]; then
  echo "missing gateway uvicorn at $GW_UVICORN" >&2
  exit 1
fi

cd "$ROOT/services/generation"
"$GEN_UVICORN" app.main:app --host 127.0.0.1 --port "$GEN_PORT" &
GEN_PID=$!

cleanup() {
  kill "$GEN_PID" 2>/dev/null || true
}
trap cleanup EXIT

ready=0
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${GEN_PORT}/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  if ! kill -0 "$GEN_PID" 2>/dev/null; then
    echo "generation process exited before becoming healthy" >&2
    exit 1
  fi
  sleep 1
done
if [[ "$ready" -ne 1 ]]; then
  echo "generation failed to become healthy on :${GEN_PORT}" >&2
  exit 1
fi

cd "$ROOT/services/gateway"
exec "$GW_UVICORN" app.main:app --host 0.0.0.0 --port "$PORT"

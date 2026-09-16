#!/usr/bin/env bash
# Single Render web dyno: Obscura CDP + generation + ingestion (Scout) + gateway.
# Defaults: gpt-oss text (NVIDIA) + Agnes image via env keys on the service.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-8000}"
GEN_PORT="${GENERATION_INTERNAL_PORT:-8003}"
INGEST_PORT="${INGESTION_INTERNAL_PORT:-8001}"
OBSCURA_PORT="${OBSCURA_PORT:-9222}"

export GENERATION_SERVICE_URL="${GENERATION_SERVICE_URL:-http://127.0.0.1:${GEN_PORT}}"
export INGESTION_SERVICE_URL="${INGESTION_SERVICE_URL:-http://127.0.0.1:${INGEST_PORT}}"
export MISSION_TEXT_MODEL="${MISSION_TEXT_MODEL:-gptoss}"
export MISSION_IMAGE_MODEL="${MISSION_IMAGE_MODEL:-agnes}"
export REDIS_URL="${REDIS_URL:-memory}"
export OBJECT_STORE_ROOT="${OBJECT_STORE_ROOT:-/data/objects}"
export BROWSER_ENGINE="${BROWSER_ENGINE:-obscura}"
# Playwright connects over WebSocket (Obscura's native CDP transport).
export OBSCURA_CDP_URL="${OBSCURA_CDP_URL:-ws://127.0.0.1:${OBSCURA_PORT}}"
mkdir -p "$OBJECT_STORE_ROOT"

# Never inject platform social cookies from env — users log in via Connect / extension.
unset LINKEDIN_COOKIES TWITTER_COOKIES X_COOKIES INSTAGRAM_COOKIES YOUTUBE_COOKIES || true

GEN_UVICORN="$ROOT/services/generation/.venv/bin/uvicorn"
INGEST_UVICORN="$ROOT/services/ingestion/.venv/bin/uvicorn"
GW_UVICORN="$ROOT/services/gateway/.venv/bin/uvicorn"
for bin in "$GEN_UVICORN" "$INGEST_UVICORN" "$GW_UVICORN"; do
  if [[ ! -x "$bin" ]]; then
    echo "missing uvicorn at $bin" >&2
    exit 1
  fi
done

OBSCURA_PID=""
if [[ "${BROWSER_ENGINE}" == "obscura" ]]; then
  if ! command -v obscura >/dev/null 2>&1; then
    echo "BROWSER_ENGINE=obscura but obscura binary not on PATH" >&2
    exit 1
  fi
  # Run from install dir so obscura-worker is found beside the binary.
  OBSCURA_HOME="$(dirname "$(readlink -f "$(command -v obscura)" 2>/dev/null || command -v obscura)")"
  cd "$OBSCURA_HOME"
  # --host 127.0.0.1: CDP stays loopback-only.
  # --quiet: Render/platform HEAD probes on :9222 otherwise spam
  #   "Unsupported HTTP method used - only GET is allowed" every second.
  obscura serve --host 127.0.0.1 --port "$OBSCURA_PORT" --quiet &
  OBSCURA_PID=$!
  cd "$ROOT"
fi

cd "$ROOT/services/generation"
"$GEN_UVICORN" app.main:app --host 127.0.0.1 --port "$GEN_PORT" &
GEN_PID=$!

cd "$ROOT/services/ingestion"
"$INGEST_UVICORN" app.main:app --host 127.0.0.1 --port "$INGEST_PORT" &
INGEST_PID=$!

cleanup() {
  kill "$GEN_PID" "$INGEST_PID" ${OBSCURA_PID:+$OBSCURA_PID} 2>/dev/null || true
}
trap cleanup EXIT

wait_healthy() {
  local name="$1" url="$2" pid="$3"
  local ready=0
  for _ in $(seq 1 90); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      ready=1
      break
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "$name process exited before becoming healthy" >&2
      exit 1
    fi
    sleep 1
  done
  if [[ "$ready" -ne 1 ]]; then
    echo "$name failed to become healthy at $url" >&2
    exit 1
  fi
}

if [[ -n "${OBSCURA_PID}" ]]; then
  # Prefer TCP listen check — avoid HEAD/non-GET probes that Obscura treats as WS upgrades.
  ready=0
  for _ in $(seq 1 60); do
    if (echo >/dev/tcp/127.0.0.1/"${OBSCURA_PORT}") >/dev/null 2>&1; then
      # Optional: confirm HTTP control plane with GET only (never HEAD/-I).
      if curl -fsS --http1.1 -X GET "http://127.0.0.1:${OBSCURA_PORT}/json/version" >/dev/null 2>&1 \
        || curl -fsS --http1.1 -X GET "http://127.0.0.1:${OBSCURA_PORT}/json/list" >/dev/null 2>&1; then
        ready=1
        break
      fi
      # Port open is enough for ws:// connect_over_cdp.
      ready=1
      break
    fi
    if ! kill -0 "$OBSCURA_PID" 2>/dev/null; then
      echo "obscura process exited before becoming ready" >&2
      exit 1
    fi
    sleep 1
  done
  if [[ "$ready" -ne 1 ]]; then
    echo "obscura failed to listen on :${OBSCURA_PORT}" >&2
    exit 1
  fi
  echo "obscura ready on ws://127.0.0.1:${OBSCURA_PORT}" >&2
fi

wait_healthy "generation" "http://127.0.0.1:${GEN_PORT}/health" "$GEN_PID"
wait_healthy "ingestion" "http://127.0.0.1:${INGEST_PORT}/health" "$INGEST_PID"

cd "$ROOT/services/gateway"
exec "$GW_UVICORN" app.main:app --host 0.0.0.0 --port "$PORT"

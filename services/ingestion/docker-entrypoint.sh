#!/bin/sh
# Start Obscura CDP then ingestion uvicorn (compose / local Docker).
# On Apple Silicon the shipped obscura-x86_64 binary often cannot run — fall back
# to Playwright Chromium so local Scout still works.
set -eu

OBSCURA_PORT="${OBSCURA_PORT:-9222}"
export BROWSER_ENGINE="${BROWSER_ENGINE:-obscura}"
export OBSCURA_CDP_URL="${OBSCURA_CDP_URL:-ws://127.0.0.1:${OBSCURA_PORT}}"

_obscura_ready=0
if [ "${BROWSER_ENGINE}" = "obscura" ] && command -v obscura >/dev/null 2>&1; then
  OBSCURA_BIN="$(command -v obscura)"
  OBSCURA_HOME="$(dirname "$OBSCURA_BIN")"
  # Resolve symlink so obscura-worker is found beside the real binary.
  if [ -L "$OBSCURA_BIN" ]; then
    OBSCURA_HOME="$(dirname "$(readlink -f "$OBSCURA_BIN" 2>/dev/null || readlink "$OBSCURA_BIN")")"
  fi
  # Probe whether the binary can even exec (x86_64 on arm64 fails immediately).
  if ! ( cd "$OBSCURA_HOME" && obscura --help >/dev/null 2>&1 ); then
    echo "obscura binary not runnable on this arch; falling back to chromium" >&2
    export BROWSER_ENGINE=chromium
  else
    ( cd "$OBSCURA_HOME" && obscura serve --host 127.0.0.1 --port "$OBSCURA_PORT" --quiet ) &
    i=0
    while [ "$i" -lt 40 ]; do
      if curl -fsS --http1.1 -X GET "http://127.0.0.1:${OBSCURA_PORT}/json/version" >/dev/null 2>&1 \
        || curl -fsS --http1.1 -X GET "http://127.0.0.1:${OBSCURA_PORT}/json/list" >/dev/null 2>&1; then
        _obscura_ready=1
        break
      fi
      i=$((i + 1))
      sleep 0.25
    done
    if [ "${_obscura_ready}" != "1" ]; then
      echo "obscura failed to listen on :${OBSCURA_PORT}; falling back to chromium" >&2
      export BROWSER_ENGINE=chromium
    else
      echo "obscura ready on ws://127.0.0.1:${OBSCURA_PORT}" >&2
    fi
  fi
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000

#!/usr/bin/env bash
# Connect agent: Xvfb + VNC + noVNC + Playwright API.
# Local Compose: exposes CONNECT_PORT (8765) + NOVNC_PORT (7900).
# Render: set PORT → nginx fronts both API and noVNC on a single public port.
set -euo pipefail

DISPLAY_NUM="${DISPLAY#:}"
DISPLAY_NUM="${DISPLAY_NUM:-99}"
export DISPLAY=":${DISPLAY_NUM}"

CONNECT_PORT="${CONNECT_PORT:-8765}"
VNC_PORT="${VNC_PORT:-5900}"
NOVNC_PORT="${NOVNC_PORT:-7900}"
PUBLIC_PORT="${PORT:-}"

echo "connect-agent: starting Xvfb on ${DISPLAY}"
Xvfb "${DISPLAY}" -screen 0 1280x900x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

NGINX_PID=""
UV_PID=""
cleanup() {
  kill "${NGINX_PID}" 2>/dev/null || true
  kill "${UV_PID}" 2>/dev/null || true
  kill "${XVFB_PID}" 2>/dev/null || true
}
trap cleanup EXIT

for _ in $(seq 1 50); do
  if [ -S "/tmp/.X11-unix/X${DISPLAY_NUM}" ]; then
    break
  fi
  sleep 0.1
done

echo "connect-agent: starting x11vnc on :${VNC_PORT}"
x11vnc -display "${DISPLAY}" -forever -shared -rfbport "${VNC_PORT}" -nopw -quiet -xkb &

NOVNC_WEB="/usr/share/novnc"
if [ ! -d "${NOVNC_WEB}" ]; then
  NOVNC_WEB="/usr/share/novnc/utils/.."
fi
echo "connect-agent: starting noVNC/websockify on :${NOVNC_PORT}"
websockify --web="${NOVNC_WEB}" "${NOVNC_PORT}" "localhost:${VNC_PORT}" &

if [[ -n "${PUBLIC_PORT}" ]]; then
  UV_HOST="127.0.0.1"
else
  UV_HOST="0.0.0.0"
fi

echo "connect-agent: uvicorn on ${UV_HOST}:${CONNECT_PORT}"
uvicorn app.main:app --host "${UV_HOST}" --port "${CONNECT_PORT}" &
UV_PID=$!

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${CONNECT_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "${UV_PID}" 2>/dev/null; then
    echo "connect-agent: uvicorn exited early" >&2
    exit 1
  fi
  sleep 0.5
done

if [[ -n "${PUBLIC_PORT}" ]]; then
  if [[ ! -f /etc/rivalradar/connect-nginx.conf ]]; then
    echo "connect-agent: missing /etc/rivalradar/connect-nginx.conf for single-port mode" >&2
    exit 1
  fi
  CONF="/tmp/connect-nginx.conf"
  sed "s/listen 8080;/listen ${PUBLIC_PORT};/" /etc/rivalradar/connect-nginx.conf > "${CONF}"
  echo "connect-agent: nginx fronting API+noVNC on :${PUBLIC_PORT}"
  nginx -c "${CONF}" &
  NGINX_PID=$!
fi

wait "${UV_PID}"

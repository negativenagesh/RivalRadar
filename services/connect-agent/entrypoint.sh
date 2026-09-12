#!/usr/bin/env bash
set -euo pipefail

DISPLAY_NUM="${DISPLAY#:}"
DISPLAY_NUM="${DISPLAY_NUM:-99}"
export DISPLAY=":${DISPLAY_NUM}"

echo "connect-agent: starting Xvfb on ${DISPLAY}"
Xvfb "${DISPLAY}" -screen 0 1280x900x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

cleanup() {
  kill "${XVFB_PID}" 2>/dev/null || true
}
trap cleanup EXIT

# Wait until the X socket exists
for _ in $(seq 1 50); do
  if [ -S "/tmp/.X11-unix/X${DISPLAY_NUM}" ]; then
    break
  fi
  sleep 0.1
done

echo "connect-agent: starting x11vnc on :${VNC_PORT:-5900}"
x11vnc -display "${DISPLAY}" -forever -shared -rfbport "${VNC_PORT:-5900}" -nopw -quiet -xkb &

NOVNC_WEB="/usr/share/novnc"
if [ ! -d "${NOVNC_WEB}" ]; then
  NOVNC_WEB="/usr/share/novnc/utils/.."
fi
echo "connect-agent: starting noVNC on :${NOVNC_PORT:-7900}"
websockify --web="${NOVNC_WEB}" "${NOVNC_PORT:-7900}" "localhost:${VNC_PORT:-5900}" &

echo "connect-agent: uvicorn on :${CONNECT_PORT:-8765}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${CONNECT_PORT:-8765}"

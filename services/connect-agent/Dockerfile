FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /build/services/connect-agent
COPY services/connect-agent/pyproject.toml services/connect-agent/uv.lock ./
COPY services/connect-agent/app ./app
RUN uv sync --no-dev

FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
      xvfb \
      x11vnc \
      novnc \
      websockify \
      fonts-liberation \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Keep the same path as the builder so the venv shebang stays valid.
WORKDIR /build/services/connect-agent
COPY --from=builder /build /build
COPY services/connect-agent/entrypoint.sh /entrypoint.sh

ENV PATH="/build/services/connect-agent/.venv/bin:$PATH" \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
    DISPLAY=:99 \
    CONNECT_PORT=8765 \
    VNC_PORT=5900 \
    NOVNC_PORT=7900 \
    CONNECT_IN_DOCKER=1 \
    PUBLIC_VIEWER_URL=http://localhost:7900/vnc.html?autoconnect=1&resize=scale

RUN playwright install --with-deps chromium \
    && chmod +x /entrypoint.sh \
    && mkdir -p /tmp/.X11-unix /data/profiles \
    && chmod 1777 /tmp/.X11-unix \
    && chmod -R a+rwX /data/profiles \
    && chmod -R a+rX /opt/ms-playwright

EXPOSE 8765 7900

HEALTHCHECK --interval=15s --timeout=5s --start-period=25s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health').read()"

ENTRYPOINT ["/entrypoint.sh"]

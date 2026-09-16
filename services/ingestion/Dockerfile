FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /build
COPY libs/agent_events ./libs/agent_events
COPY services/ingestion ./services/ingestion

WORKDIR /build/services/ingestion
RUN uv sync --no-install-project --no-dev
RUN uv sync --no-dev

FROM python:3.12-slim AS runtime

ENV CONNECT_IN_DOCKER=1 \
    BROWSER_ENGINE=obscura \
    OBSCURA_CDP_URL=http://127.0.0.1:9222 \
    OBSCURA_VERSION=v0.2.2

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 appuser

RUN mkdir -p /opt/obscura \
    && curl -fsSL -o /tmp/obscura.tar.gz \
      "https://github.com/h4ckf0r0day/obscura/releases/download/${OBSCURA_VERSION}/obscura-x86_64-linux.tar.gz" \
    && tar -xzf /tmp/obscura.tar.gz -C /opt/obscura \
    && chmod +x /opt/obscura/obscura /opt/obscura/obscura-worker \
    && ln -sf /opt/obscura/obscura /usr/local/bin/obscura \
    && rm -f /tmp/obscura.tar.gz \
    && mkdir -p /data/objects \
    && chown -R appuser:appuser /data/objects /opt/obscura

WORKDIR /build/services/ingestion
COPY --from=builder --chown=appuser:appuser /build /build
ENV PATH="/build/services/ingestion/.venv/bin:/usr/local/bin:$PATH"

COPY --chown=appuser:appuser services/ingestion/docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER appuser

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]

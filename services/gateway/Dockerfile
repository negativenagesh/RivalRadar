FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /build
COPY libs/agent_events ./libs/agent_events
COPY services/gateway ./services/gateway

WORKDIR /build/services/gateway
RUN uv sync --no-install-project --no-dev
RUN uv sync --no-dev

FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 1000 appuser
WORKDIR /build/services/gateway

COPY --from=builder --chown=appuser:appuser /build /build
ENV PATH="/build/services/gateway/.venv/bin:$PATH"

USER appuser

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

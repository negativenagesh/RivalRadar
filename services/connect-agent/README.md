# RivalRadar Connect Agent

Playwright helper for platform login (Instagram, LinkedIn, X, TikTok, Threads).
RivalRadar never asks for passwords — when you click **I've logged in**, cookies +
`storage_state` are vaulted in the gateway.

## Stay signed in

Each platform gets a **persistent Chromium profile** under `/data/profiles/{platform}`
(Compose volume `connect_profiles`). Reconnect reopens that profile and also re-seeds
vaulted cookies, so you usually stay logged in.

## Default: Docker Compose

```bash
docker compose up -d --build
```

- API: `http://localhost:8765`
- Viewer (noVNC): `http://localhost:7900`
- Profiles volume: `connect_profiles`

## Optional: native Mac window

```bash
cd services/connect-agent
uv sync && uv run playwright install chromium
CONNECT_PROFILE_ROOT=./.profiles uv run uvicorn app.main:app --host 127.0.0.1 --port 8765
```

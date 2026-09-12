# RivalRadar Connect Agent

Playwright helper that opens a real browser for platform login (Instagram, LinkedIn, X,
TikTok, Threads). RivalRadar never asks for passwords or pasted cookies — when you click
**I've logged in**, the agent dumps cookies to the gateway vault.

## Default: Docker Compose (recommended)

`connect-agent` starts with the rest of the backend:

```bash
docker compose up -d --build
```

- API: `http://localhost:8765`
- Browser viewer (noVNC): `http://localhost:7900`

Gateway talks to it at `http://connect-agent:8765`. Click **Connect** in Mission Control and
sign in inside the noVNC tab.

## Optional: native Mac window

If you prefer a real Chromium window on the host instead of noVNC:

```bash
cd services/connect-agent
uv sync
uv run playwright install chromium
uv run uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Then point gateway at the host agent:

```bash
CONNECT_AGENT_URL=http://host.docker.internal:8765 docker compose up -d gateway
```

# RivalRadar Connect Agent

Headed Playwright helper that opens a real browser window for platform login
(Instagram, LinkedIn, X, TikTok, Threads). RivalRadar never asks for passwords
or pasted cookies — when you click **I've logged in**, the agent dumps cookies
to the gateway vault.

## Run on your Mac (required)

Docker cannot show a headed browser. Keep this process running on the host:

```bash
cd services/connect-agent
uv sync
uv run playwright install chromium
uv run uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Gateway (in Compose) reaches it via `host.docker.internal:8765`.

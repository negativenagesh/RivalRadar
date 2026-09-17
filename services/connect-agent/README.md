# RivalRadar Connect Agent

Playwright helper for **local** platform login (Instagram, LinkedIn, X, TikTok, Threads)
via headed Chromium + **noVNC** (browser-in-browser). RivalRadar never asks for passwords —
when you click **I've logged in**, cookies + `storage_state` are vaulted in the gateway.

> Scout uses Obscura/Chromium separately. **Connect never uses Obscura** — only Playwright.

## Stay signed in

Each platform gets a **persistent Chromium profile** under `/data/profiles/{platform}`
(Compose volume `connect_profiles`). Reconnect reopens that profile and also re-seeds
vaulted cookies, so you usually stay logged in.

## Human-like settle (scroll + timeouts)

After opening the login URL (and again before dumping cookies), the agent applies the same
style of pacing Scout uses: jittered pauses and occasional mouse-wheel scrolls. A sparse
idle loop may scroll while you are on the noVNC viewer, but **never while an input is
focused**, so typing is not interrupted.

Disable with `CONNECT_HUMAN_PACING=0`.

## Default: Docker Compose (noVNC)

```bash
docker compose up -d --build connect-agent gateway
```

- API: `http://localhost:8765`
- Viewer (noVNC): `http://localhost:7900/vnc.html?autoconnect=1&resize=scale`
- Profiles volume: `connect_profiles`

Flow: Mission → Connect → **Browser (noVNC)** for LinkedIn / Instagram / X / … → sign in
inside the embedded viewer → **I've logged in** → cookies vaulted.

## Optional: native Mac window

```bash
cd services/connect-agent
uv sync && uv run playwright install chromium
CONNECT_PROFILE_ROOT=./.profiles uv run uvicorn app.main:app --host 127.0.0.1 --port 8765
```

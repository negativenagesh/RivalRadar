# Deploy RivalRadar: Vercel (frontend) + Render (API)

## Architecture
- **Vercel**: Next.js app in `frontend/`
- **Render**: one Docker web service (`deploy/Dockerfile.api`) running **Obscura CDP + generation + ingestion (Scout) + gateway**
  - Scout browser: **Obscura** (~30 MB RAM) via Playwright CDP — not Chromium (fits free 512 MB)
  - Default models: **gpt-oss** (`NVIDIA_API_KEY`) + **Agnes** (`AGNES_API_KEY`)
- **Supabase** (optional): visitor pageviews (`supabase/migrations/001_visitor_pageviews.sql`)
- **Connect / social login**: prefer the **Chrome extension** (`extensions/rivalradar-connect`) + pairing code. noVNC Connect browser remains as fallback. No LinkedIn/X/IG cookies are loaded from env on deploy.

## Render env vars (what to paste)

### Required (you must set)
| Key | Example / where to get it |
|-----|---------------------------|
| `NVIDIA_API_KEY` | [build.nvidia.com](https://build.nvidia.com) → API key for gpt-oss |
| `AGNES_API_KEY` | Agnes dashboard → API key for images |
| `CORS_ORIGINS` | `https://YOUR-APP.vercel.app,http://localhost:3000` (no spaces needed; commas OK) |

### Auto-filled by Blueprint (leave alone)
| Key | Value |
|-----|--------|
| `DATABASE_URL` | From `rivalradar-db` |
| `CONNECTION_VAULT_KEY` | Auto-generated |
| `MISSION_TEXT_MODEL` | `gptoss` |
| `MISSION_IMAGE_MODEL` | `agnes` |
| `GENERATION_SERVICE_URL` | `http://127.0.0.1:8003` |
| `INGESTION_SERVICE_URL` | `http://127.0.0.1:8001` |
| `OBJECT_STORE_ROOT` | `/data/objects` |
| `BROWSER_ENGINE` | `obscura` |
| `OBSCURA_CDP_URL` | `ws://127.0.0.1:9222` |
| `REDIS_URL` | `memory` (fine for Mission; Scout live WS is proxied gateway→ingestion so FakeRedis is OK) |
| `DISALLOW_ENV_SOCIAL_COOKIES` | `true` |

### Optional (analytics)
| Key | Notes |
|-----|--------|
| `SUPABASE_URL` | Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | **service_role** only — never put in Vercel |

### Do NOT set
- Any LinkedIn / X / Instagram / YouTube **cookies** or session tokens
- `GEMINI_API_KEY` unless you want Gemini instead of gpt-oss/Agnes defaults

## 1. Supabase (optional)
1. Create a project.
2. Run `supabase/migrations/001_visitor_pageviews.sql` in the SQL editor.
3. Copy Project URL + service_role key into Render env later.

## 2. Render (step by step)
1. [dashboard.render.com](https://dashboard.render.com) → **New +** → **Blueprint**
2. Connect GitHub repo **RivalRadar**, branch **main** (detects `render.yaml`)
3. When prompted, paste:
   - `NVIDIA_API_KEY`
   - `AGNES_API_KEY`
   - `CORS_ORIGINS` = your Vercel URL + localhost (see table)
4. **Apply** — creates `rivalradar-api` + `rivalradar-db`
5. Wait for the first Docker deploy (Obscura binary is small — faster than former Playwright Chromium image). Health check is `/ready`.
6. Copy the service URL, e.g. `https://rivalradar-api.onrender.com`
7. Smoke test:
   ```bash
   curl https://YOUR-API.onrender.com/health
   curl https://YOUR-API.onrender.com/ready
   # expect generation=ok and ingestion=ok
   curl -X POST https://YOUR-API.onrender.com/ingestion/runs \
     -H 'Content-Type: application/json' -d '{"targets":[]}'
   # expect 202 JSON with run_id (not 500 / Failed to fetch)
   ```

Free tier sleeps after idle. The navbar **Waking API…** chip polls until green. First Start Scout after sleep can take 1–2 minutes. Live run status polls every ~4s (rate-limit safe).

## 3. Vercel
1. Import repo → **Root Directory** = `frontend`
2. Env: `NEXT_PUBLIC_GATEWAY_URL=https://YOUR-API.onrender.com`
3. Deploy / redeploy after changing the gateway URL (build-time inlined).

## 4. Connect (preferred: Chrome extension)

Mission creative works without Connect. For LinkedIn / X / Instagram / TikTok / Threads:

### Fast path — Chrome extension (no noVNC cold start)

1. Deploy / merge so gateway has `POST /connect/pairing` + `POST /connections/{platform}/quick` (this release).
2. No new Render env vars required for the extension path.
3. On your machine: Chrome → `chrome://extensions` → Developer mode → **Load unpacked** → `extensions/rivalradar-connect`
4. In the extension popup, set **API URL** to your Render gateway (e.g. `https://rivalradar-api-fl5j.onrender.com`)
5. On Vercel RivalRadar → Connect → **Extension (fast)** → copy code → paste in extension → Connect
6. Dialog auto-closes when status is `connected`

### Fallback — Connect browser (noVNC) on Render

1. Blueprint deploys **`rivalradar-connect`** (Playwright + noVNC on one port).
2. Open that service → copy its URL, e.g. `https://rivalradar-connect-xxxx.onrender.com`
3. On **rivalradar-api** → Environment, set:
   - `CONNECT_AGENT_URL=https://rivalradar-connect-xxxx.onrender.com`
   - `CONNECT_VIEWER_URL=https://rivalradar-connect-xxxx.onrender.com/vnc.html?autoconnect=1&resize=scale`
4. Save (API restarts). On the site use Connect → **Browser (noVNC)** → sign in → **I've logged in**.

If `rivalradar-connect` crashes / OOM on free tier, prefer the extension path or upgrade Connect to **Starter**. Locally: `docker compose up -d connect-agent`.

## 5. Optional full stack (Scout / stage-post)

## Rate limits (per edge IP)
- `/creative/generate` 20/hour
- `/creative/publish-plan` 30/hour
- `/intel/report` 15/hour
- `/connect/pairing` 30/hour
- `/connections/` 40/hour
- other API ~180/hour

## Checklist
- [ ] Render: NVIDIA + Agnes + CORS set
- [ ] `/ready` returns generation ok
- [ ] Vercel `NEXT_PUBLIC_GATEWAY_URL` matches Render
- [ ] Navbar shows **API online** after cold start
- [ ] (Optional) Supabase table + keys on Render
- [ ] No social cookies in any env
- [ ] Chrome extension loaded; API URL points at Render gateway
- [ ] (Optional) Connect agent URL + viewer URL if using noVNC fallback

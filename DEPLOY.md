# Deploy RivalRadar: Vercel (frontend) + Render (API)

## Architecture
- **Vercel**: Next.js app in `frontend/`
- **Render**: one Docker web service (`deploy/Dockerfile.api`) running **generation + gateway**
  - Default models: **gpt-oss** (`NVIDIA_API_KEY`) + **Agnes** (`AGNES_API_KEY`)
- **Supabase** (optional): visitor pageviews (`supabase/migrations/001_visitor_pageviews.sql`)
- **Connect / social login**: users sign in themselves inside the Connect headless browser.
  No LinkedIn/X/IG cookies are loaded from env on deploy.

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
| `REDIS_URL` | `memory` (fine for Mission; set Upstash URL later for live scout WS) |
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
5. Wait for the first Docker deploy (several minutes). Health check is `/ready`.
6. Copy the service URL, e.g. `https://rivalradar-api.onrender.com`
7. Smoke test:
   ```bash
   curl https://YOUR-API.onrender.com/health
   curl https://YOUR-API.onrender.com/ready
   ```

Free tier sleeps after idle. The navbar **Waking API…** chip polls until green.

## 3. Vercel
1. Import repo → **Root Directory** = `frontend`
2. Env: `NEXT_PUBLIC_GATEWAY_URL=https://YOUR-API.onrender.com`
3. Deploy / redeploy after changing the gateway URL (build-time inlined).

## 4. Connect browser (LinkedIn / X / Instagram) on Render

Mission creative works without Connect. To open the noVNC login browser from Vercel:

1. Blueprint deploys **`rivalradar-connect`** (Playwright + noVNC on one port).
2. Open that service → copy its URL, e.g. `https://rivalradar-connect-xxxx.onrender.com`
3. On **rivalradar-api** → Environment, set:
   - `CONNECT_AGENT_URL=https://rivalradar-connect-xxxx.onrender.com`
   - `CONNECT_VIEWER_URL=https://rivalradar-connect-xxxx.onrender.com/vnc.html?autoconnect=1&resize=scale`
4. Save (API restarts). Click **Connect LinkedIn** on the Vercel site → a Connect browser tab should open.
5. Sign in yourself → **I've logged in**.

If `rivalradar-connect` crashes / OOM on free tier, upgrade that service to **Starter** (Chromium needs RAM). Locally you can instead run `docker compose up -d connect-agent` and point a tunnel, or use the full Compose stack.

## 5. Optional full stack (Scout / stage-post)

## Rate limits (per edge IP)
- `/creative/generate` 20/hour
- `/creative/publish-plan` 30/hour
- `/intel/report` 15/hour
- other API ~180/hour

## Checklist
- [ ] Render: NVIDIA + Agnes + CORS set
- [ ] `/ready` returns generation ok
- [ ] Vercel `NEXT_PUBLIC_GATEWAY_URL` matches Render
- [ ] Navbar shows **API online** after cold start
- [ ] (Optional) Supabase table + keys on Render
- [ ] No social cookies in any env

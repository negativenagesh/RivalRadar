# Deploy RivalRadar: Vercel (frontend) + Render (API)

## Architecture
- **Vercel**: Next.js app in `frontend/`
- **Render**: one Docker web service (`deploy/Dockerfile.api`) running **generation + gateway**
  - Default models: **gpt-oss** (`NVIDIA_API_KEY`) + **Agnes** (`AGNES_API_KEY`)
- **Supabase**: visitor pageviews (`supabase/migrations/001_visitor_pageviews.sql`)
- **Connect / social login**: users sign in themselves inside the Connect headless browser.
  No LinkedIn/X/IG cookies are loaded from env on deploy.

## 1. Supabase
1. Create a project.
2. Run `supabase/migrations/001_visitor_pageviews.sql` in the SQL editor.
3. Copy **Project URL** + **service_role** key (server only — never put in Vercel `NEXT_PUBLIC_*`).

## 2. Render
1. New Blueprint → `render.yaml` (or Web Service from `deploy/Dockerfile.api`, context `.`).
2. Set secrets in the dashboard:
   - `NVIDIA_API_KEY` — your NVIDIA NIM key (gpt-oss default)
   - `AGNES_API_KEY` — your Agnes key (image default)
   - `CONNECTION_VAULT_KEY` — long random string
   - `CORS_ORIGINS` — `https://YOUR-APP.vercel.app,http://localhost:3000`
   - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
   - `REDIS_URL` — optional; live scout needs Redis (Upstash free works)
3. Note the public API URL, e.g. `https://rivalradar-api.onrender.com`.

Free tier sleeps after idle. The navbar **Waking API…** chip polls `/health` + `/ready` until green.

## 3. Vercel
1. Import repo → root directory `frontend`.
2. Env (Build + Runtime):
   - `NEXT_PUBLIC_GATEWAY_URL=https://rivalradar-api.onrender.com`
3. Deploy. Rebuild after changing the gateway URL (inlined at build time).

## 4. Optional full stack (Scout / stage-post / Connect)
Mission creative + publish captions + intel work on the Render API alone.
Scout, stage-post, comment-drop, and Connect noVNC still need `ingestion` + `connect-agent`
(Docker Compose / a paid instance with Playwright + shm). Point
`INGESTION_SERVICE_URL`, `CONNECT_AGENT_URL`, `CONNECT_VIEWER_URL` when those are up.

## 5. Rate limits (per visitor fingerprint)
Shared NVIDIA/Agnes keys stay healthy under multi-tenant use, e.g.:
- `/creative/generate` 20/hour
- `/creative/publish-plan` 30/hour
- `/intel/report` 15/hour
- other API ~180/hour

Identity = hash(IP + User-Agent + `rr_vid`).

## Checklist
- [ ] Supabase table created
- [ ] Render env: NVIDIA + Agnes + CORS + vault key
- [ ] Vercel `NEXT_PUBLIC_GATEWAY_URL` matches Render
- [ ] Navbar shows **API online** after cold start
- [ ] Pageviews appear in `visitor_pageviews`
- [ ] No social cookies in any env file

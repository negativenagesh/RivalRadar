# Frontend

Next.js (App Router, TypeScript, Tailwind, shadcn/ui, Motion) — the only client of the `gateway` service.

## Pages

- `/` — landing page.
- `/digest` — weekly trend & gap intelligence: clusters ranked by engagement, trending/gap themes, a "Generate drafts" action that starts a background pipeline run and polls it to completion.
- `/review` — draft queue: caption, image concept, compliance verdict, and Approve/Edit/Reject actions per draft.

## Visual direction

Dark-mode-first ("warm/electric dark"): near-black background, one saturated accent (electric lime, `oklch(0.87 0.24 128)`) carrying all primary emphasis, a warm coral/orange (`oklch(0.7 0.19 35)`) for compliance-flag and destructive states, bold Geist Sans display type, subtle Motion entrance/hover animation. Chosen deliberately over a gray-and-blue SaaS look — see the root `README.md`'s "why these technical choices" section.

## Run standalone

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Requires the `gateway` service (and its own dependencies) running at `NEXT_PUBLIC_GATEWAY_URL` (default `http://localhost:8000`).

## Env vars

See [.env.example](.env.example). `NEXT_PUBLIC_GATEWAY_URL` is inlined at **build time** (it's a `NEXT_PUBLIC_*` var read client-side), not read at container runtime — the Dockerfile takes it as a build arg, and `docker-compose.yml` passes it through `args`, not `environment`.

## Lint / typecheck / build

```bash
npm run lint
npx tsc --noEmit
npm run build
```
